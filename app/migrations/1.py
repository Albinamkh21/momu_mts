


CREATE INDEX idx_track_right_perf ON track_right (right_usage_type_id, track_id, right_category_id, share_percentage);


CREATE TABLE report_track_rights_distribution (
    id BIGSERIAL PRIMARY KEY,
    report_id BIGINT NOT NULL,          -- Прямая ссылка на метаданные отчета
    staging_id BIGINT NOT NULL,         -- Исходная строка стриминга
    track_id BIGINT NOT NULL,
    right_holder_id BIGINT NOT NULL,
    right_category_id INT NOT NULL,     -- Конкретная категория (1 - Авторские, 2 - Смежные)
    right_usage_type_id INT NOT NULL,
    
    original_share_percentage NUMERIC(10, 4) NOT NULL,
    calculated_share_percentage NUMERIC(10, 4) NOT NULL, -- Доля, которая уйдет в Excel
    final_payout_amount NUMERIC(15, 6) NOT NULL,          -- Чистые деньги правообладателя
    is_normalized BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для моментальной выборки при экспорте
CREATE INDEX idx_rights_dist_report ON report_track_rights_distribution(report_id);

CREATE INDEX IF NOT EXISTS idx_rtrd_report_staging ON report_track_rights_distribution (report_id, staging_id);




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
GROUP BY t.track_id, t.label_own_code;

CREATE UNIQUE INDEX idx_mv_track_rights_prev__track_id ON mv_track_rights_prev(track_id);

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
LEFT JOIN parent_rights p ON p.parent_code = t.base_code;

CREATE UNIQUE INDEX idx_mv_track_rights__track_id ON mv_track_rights(track_id);


CREATE INDEX IF NOT EXISTS idx_mv_track_extended_sort ON mv_track_extended(label_id, track_id);
CREATE INDEX IF NOT EXISTS idx_mv_track_rights_sort ON mv_track_rights(base_code);
SET work_mem = '256MB';



