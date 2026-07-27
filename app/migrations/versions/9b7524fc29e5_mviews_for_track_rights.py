"""mviews_for_track_rights

Revision ID: 9b7524fc29e5
Revises: b378978c23eb
Create Date: 2026-07-09
"""
from alembic import context, op
import sqlalchemy as sa


revision = '9b7524fc29e5'
down_revision = 'd2b3c4e5f6a7'  
branch_labels = None
depends_on = None


def upgrade() -> None:
    tags = context.get_x_argument(as_dictionary=True)
    if tags.get("run_optional") != "true":
        print(
            f"⏩ Миграция {revision} пропущена по умолчанию (требуется флаг -x run_optional=true)"
        )
        return

    # Изменяем work_mem локально для сессии
    op.execute("SET LOCAL work_mem = '256MB';")

    # 1. Индекс на существующую таблицу track_right
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_track_right_perf 
        ON track_right (right_usage_type_id, track_id, right_category_id, share_percentage);
    """)

    # 2. Materialized View: mv_track_extended
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_matviews WHERE schemaname = 'public' AND matviewname = 'mv_track_extended') THEN
                CREATE MATERIALIZED VIEW mv_track_extended AS
                WITH authors_flat AS (
                    SELECT 
                        tc.track_id,
                        string_agg(DISTINCT p.full_name::text, ', '::text) FILTER (WHERE tc.role::text = 'artist_name'::text) AS artist_name,
                        string_agg(DISTINCT p.full_name::text, ', '::text) FILTER (WHERE tc.role::text = 'track_artist_name'::text) AS track_artist_name,
                        string_agg(DISTINCT p.full_name::text, ', '::text) FILTER (WHERE tc.role::text = 'composer'::text) AS composer,
                        string_agg(DISTINCT p.full_name::text, ', '::text) FILTER (WHERE tc.role::text = 'lyricist'::text) AS lyricist,
                        string_agg(DISTINCT p.full_name::text, ', '::text) FILTER (WHERE tc.role::text = 'authors'::text) AS authors
                    FROM track_contribution tc
                    JOIN person p ON p.id = tc.person_id
                    GROUP BY tc.track_id
                )
                SELECT DISTINCT ON (t.id) 
                    t.id AS track_id,
                    t.isrc::text AS isrc,
                    t.title AS track_name,  
                    t.label_own_code::text AS label_own_code,
                    af.artist_name,
                    af.track_artist_name,
                    af.composer,
                    af.lyricist,
                    af.authors, 
                    tl.label_id,
                    COALESCE(l.name, ''::citext)::text AS label_name,
                    COALESCE(r.upc, ''::character varying)::text AS upc,
                    t.meta ->> 'genre'::text AS genre_name,
                    COALESCE(r.title, ''::text) AS album_name,
                    t.meta ->> 'track_number'::text AS track_number,
                    CASE 
                        WHEN t.explicit THEN 'Да'::text 
                        ELSE 'Нет'::text 
                    END AS explicit,
                    t.duration::text AS duration,
                    t.created_at::text AS created_at
                FROM track t
                LEFT JOIN authors_flat af ON af.track_id = t.id
                LEFT JOIN track_release tr ON tr.track_id = t.id
                LEFT JOIN release r ON r.id = tr.release_id
                LEFT JOIN track_label tl ON tl.track_id = t.id
                LEFT JOIN label l ON l.id = tl.label_id
                ORDER BY t.id
                WITH NO DATA;
            END IF;
        END $$;
    """)

    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx__mv_track_extended__track_id ON mv_track_extended(track_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_track_extended_sort ON mv_track_extended(label_id, track_id);")

    # 3. Materialized View: mv_track_rights_prev
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_matviews WHERE schemaname = 'public' AND matviewname = 'mv_track_rights_prev') THEN
                CREATE MATERIALIZED VIEW mv_track_rights_prev AS
                SELECT 
                    t.track_id,
                    t.label_own_code,
                    CASE 
                        WHEN t.label_own_code LIKE '%-%' THEN REGEXP_REPLACE(t.label_own_code, '-[A-Za-z0-9]+$', '') 
                        ELSE t.label_own_code 
                    END AS base_code,
                    MAX(CASE WHEN tr.right_category_id = 2 AND tr.right_usage_type_id = 4 THEN tr.share_percentage ELSE 0 END) AS rel_int,
                    MAX(CASE WHEN tr.right_category_id = 2 AND tr.right_usage_type_id = 3 THEN tr.share_percentage ELSE 0 END) AS rel_mob,
                    MAX(CASE WHEN tr.right_category_id = 2 AND tr.right_usage_type_id = 2 THEN tr.share_percentage ELSE 0 END) AS rel_pub,
                    MAX(CASE WHEN tr.right_category_id = 1 AND tr.right_usage_type_id = 4 THEN tr.share_percentage ELSE 0 END) AS auth_int,
                    MAX(CASE WHEN tr.right_category_id = 1 AND tr.right_usage_type_id = 3 THEN tr.share_percentage ELSE 0 END) AS auth_mob,
                    MAX(CASE WHEN tr.right_category_id = 1 AND tr.right_usage_type_id = 2 THEN tr.share_percentage ELSE 0 END) AS auth_pub,
                    string_agg(DISTINCT CASE WHEN tr.right_category_id = 2 THEN l.name END, ', ') AS rel_holders,
                    string_agg(DISTINCT CASE WHEN tr.right_category_id = 1 THEN l.name END, ', ') AS auth_holders
                FROM mv_track_extended t
                LEFT JOIN track_right tr ON tr.track_id = t.track_id
                LEFT JOIN right_holder rh ON rh.id = tr.right_holder_id
                LEFT JOIN label l ON l.id = rh.label_id
                GROUP BY t.track_id, t.label_own_code
                WITH NO DATA;
            END IF;
        END $$;
    """)

    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_track_rights_prev__track_id ON mv_track_rights_prev(track_id);")

    # 4. Materialized View: mv_track_rights
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_matviews WHERE schemaname = 'public' AND matviewname = 'mv_track_rights') THEN
                CREATE MATERIALIZED VIEW mv_track_rights AS
                WITH parent_rights AS (
                    SELECT 
                        label_own_code AS parent_code,
                        MAX(auth_int) AS parent_auth_int,
                        MAX(auth_mob) AS parent_auth_mob,
                        MAX(auth_pub) AS parent_auth_pub,
                        string_agg(DISTINCT auth_holders, ', ') AS parent_auth_holders
                    FROM mv_track_rights_prev
                    WHERE label_own_code = base_code
                    GROUP BY label_own_code
                )
                SELECT 
                    t.track_id,
                    t.label_own_code,
                    t.base_code,
                    t.rel_int,
                    t.rel_mob,
                    t.rel_pub,
                    t.rel_holders,
                    CASE 
                        WHEN t.label_own_code != t.base_code AND (t.auth_int = 0 AND t.auth_mob = 0 AND t.auth_pub = 0)
                        THEN COALESCE(p.parent_auth_int, 0)
                        ELSE t.auth_int 
                    END AS auth_int,
                    CASE 
                        WHEN t.label_own_code != t.base_code AND (t.auth_int = 0 AND t.auth_mob = 0 AND t.auth_pub = 0)
                        THEN COALESCE(p.parent_auth_mob, 0)
                        ELSE t.auth_mob 
                    END AS auth_mob,
                    CASE 
                        WHEN t.label_own_code != t.base_code AND (t.auth_int = 0 AND t.auth_mob = 0 AND t.auth_pub = 0)
                        THEN COALESCE(p.parent_auth_pub, 0)
                        ELSE t.auth_pub 
                    END AS auth_pub,
                    CASE 
                        WHEN t.label_own_code != t.base_code AND (t.auth_int = 0 AND t.auth_mob = 0 AND t.auth_pub = 0)
                        THEN p.parent_auth_holders
                        ELSE t.auth_holders 
                    END AS auth_holders
                FROM mv_track_rights_prev t
                LEFT JOIN parent_rights p ON p.parent_code = t.base_code
                WITH NO DATA;
            END IF;
        END $$;
    """)

    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_track_rights__track_id ON mv_track_rights(track_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_track_rights_sort ON mv_track_rights(base_code);")


def downgrade() -> None:
    tags = context.get_x_argument(as_dictionary=True)
    if tags.get("run_optional") != "true":
        print(
            f"⏩ Откат миграции {revision} пропущен (требуется флаг -x run_optional=true)"
        )
        return

    # Удаляем views в обратном порядке (с CASCADE на случай зависимых объектов)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_track_rights CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_track_rights_prev CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_track_extended CASCADE;")

    # Удаляем индекс с базовой таблицы
    op.execute("DROP INDEX IF EXISTS idx_track_right_perf;")