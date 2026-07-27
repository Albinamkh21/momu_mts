-- Включаем расширения
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS citext;

--------------------------------------------------------------------------------
-- 1. STAGING LAYER (Хранилище сырых данных)
--------------------------------------------------------------------------------
CREATE TABLE staging_catalog (
    id BIGSERIAL PRIMARY KEY,
    import_batch_id UUID DEFAULT gen_random_uuid(),
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    
    upc TEXT, isrc TEXT, track_name TEXT, genre_name TEXT, album_name TEXT,
    album_single TEXT, track_number TEXT, artist_name TEXT, track_artist_name TEXT,
    composer TEXT, lyricist TEXT, authors TEXT, explicit TEXT, duration TEXT,
    label_name TEXT, total_author_right TEXT, right_id TEXT, author_right_1 TEXT,
    ar_label_treaty_number_1 TEXT, author_right_2 TEXT, ar_label_treaty_number_2 TEXT,
    author_right_3 TEXT, ar_label_treaty_number_3 TEXT, total_related_right TEXT,
    related_right_id_1 TEXT, rr_label_treaty_number_1 TEXT, related_right_id_2 TEXT,
    rr_label_treaty_number_2 TEXT, related_right_id_3 TEXT, rr_label_treaty_number_3 TEXT,
    types_of_rights TEXT, countries TEXT, create_date TEXT, release_date TEXT,
    sales_start_date TEXT, has_ringtone TEXT, ringtone_upc TEXT, ringtone_isrc TEXT,
    has_vclip TEXT, vclip_isrc TEXT, video_upc TEXT, has_lyrics TEXT, has_ttml TEXT,
    effective_date TEXT, termination_date TEXT, active_inactive TEXT, resource_reference TEXT,
    track_id TEXT, track_song_id TEXT,
    upload_id TEXT, user_id TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE staging_catalog_v2 (
    id BIGSERIAL PRIMARY KEY,
    import_batch_id UUID DEFAULT gen_random_uuid(),
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    track_id TEXT, track_song_id TEXT,
    upc TEXT, isrc TEXT, track_name TEXT, genre_name TEXT, album_name TEXT,
    album_single TEXT, track_number TEXT, artist_name TEXT, track_artist_name TEXT,
    composer TEXT, lyricist TEXT, authors TEXT, explicit TEXT, duration TEXT,
    label_name TEXT, right_id TEXT, author_right_INT TEXT, author_right_MOB TEXT, author_right_PUB TEXT,  ar_label_treaty_number TEXT,
    related_right_id_INT TEXT, related_right_id_MOB TEXT, related_right_id_PUB TEXT,  rr_label_treaty_number TEXT,
    types_of_rights TEXT, countries TEXT, create_date TEXT, release_date TEXT,
    sales_start_date TEXT, has_ringtone TEXT, ringtone_upc TEXT, ringtone_isrc TEXT,
    has_vclip TEXT, vclip_isrc TEXT, video_upc TEXT, has_lyrics TEXT, has_ttml TEXT,
    effective_date TEXT, termination_date TEXT, active_inactive TEXT, resource_reference TEXT,
    upload_id TEXT, user_id TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


--------------------------------------------------------------------------------
-- 2. CORE LAYER (Нормализованная рабочая база)
--------------------------------------------------------------------------------

-- Справочники
CREATE TABLE label (
    id SERIAL PRIMARY KEY,
    name CITEXT NOT NULL UNIQUE,
    composition_count INT DEFAULT 0,
    phonogram_count INT DEFAULT 0

);


CREATE TABLE right_category (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);


CREATE TABLE right_usage_type (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL, 
    name VARCHAR(50),
    description TEXT
);


CREATE TABLE right_holder (
    id SERIAL PRIMARY KEY,
   name CITEXT NOT NULL UNIQUE,
    label_id INTEGER REFERENCES label(id),
    effective_date DATE, termination_date DATE    
);

CREATE TABLE person (
    id BIGSERIAL PRIMARY KEY,
    full_name CITEXT UNIQUE NOT NULL
);


CREATE TABLE contract (
    id BIGSERIAL PRIMARY KEY,
    right_holder_id INTEGER REFERENCES right_holder(id),
    treaty_number VARCHAR(255) UNIQUE NOT NULL,
    effective_date DATE,
    termination_date DATE
);


CREATE TABLE release (
    id BIGSERIAL PRIMARY KEY,
    upc VARCHAR(20) UNIQUE,
    title TEXT NOT NULL,
    release_date DATE,
    label_id INTEGER REFERENCES label(id),
    status VARCHAR(20) DEFAULT 'Active'
);

CREATE TABLE track (
    id BIGSERIAL PRIMARY KEY,
    release_id BIGINT REFERENCES release(id),
    isrc VARCHAR(20),
    label_own_code VARCHAR(20),
    label_id INTEGER REFERENCES label(id),
    title TEXT NOT NULL,
    duration INTERVAL,
    explicit BOOLEAN DEFAULT FALSE,
    resource_reference TEXT,
    meta JSONB, -- Сюда всё после 35 колонки (ringtone, vclip, ttml)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE track_contribution (
    id BIGSERIAL PRIMARY KEY,
    track_id BIGINT REFERENCES track(id) ON DELETE CASCADE,
    person_id BIGINT REFERENCES person(id),
    role VARCHAR(50) NOT NULL -- 'performer', 'composer', 'lyricist', 'author'
);

CREATE TABLE track_right (
    id BIGSERIAL PRIMARY KEY,
    track_id BIGINT NOT NULL REFERENCES track(id) ON DELETE CASCADE,
    contract_id BIGINT NULL REFERENCES contract(id),
    right_holder_id INTEGER REFERENCES right_holder(id),
    right_category_id INTEGER REFERENCES right_category(id),
    right_usage_type_id INTEGER REFERENCES right_usage_type(id),
    share_percentage NUMERIC(5,2) CHECK (share_percentage BETWEEN 0 AND 100),
    region_id integer REFERENCES region(id)
);

CREATE TABLE track_label (
    id SERIAL PRIMARY KEY,
    track_id INTEGER REFERENCES track(id) ON DELETE CASCADE,
    label_id INTEGER REFERENCES label(id), 
      UNIQUE (track_id, label_id)
);

ALTER TABLE track_label 
ADD CONSTRAINT track_label_unique_idx 
UNIQUE (track_id, label_id);




CREATE INDEX idx_staging_v2_upload_id ON staging_catalog_v2(upload_id);
CREATE INDEX idx_staging_v2_isrc ON staging_catalog_v2(isrc);
CREATE INDEX idx_staging_v2_upc ON staging_catalog_v2(upc);
CREATE INDEX idx_staging_v2_label_name ON staging_catalog_v2(label_name);


CREATE INDEX idx_staging_upload_id ON staging_catalog(upload_id);

CREATE INDEX idx_track_isrc ON track(isrc);
CREATE INDEX idx_track_title_trgm ON track USING gin (title gin_trgm_ops);
CREATE INDEX idx_person_name_trgm ON person USING gin (full_name gin_trgm_ops);


CREATE TABLE IF NOT EXISTS track_release (
    track_id INTEGER NOT NULL REFERENCES track(id) ON DELETE CASCADE,
    release_id INTEGER NOT NULL REFERENCES release(id) ON DELETE CASCADE,
    track_number TEXT, 
    
    PRIMARY KEY (track_id, release_id)
);


CREATE INDEX IF NOT EXISTS idx_track_release_release_id ON track_release(release_id);
CREATE INDEX IF NOT EXISTS idx_track_release_track_id ON track_release(track_id);


















CREATE TABLE finding_source (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL, 
    name VARCHAR(50),
    description TEXT
);

insert into finding_source (code, name) values 
('ISRC', 'ISRC'),
('LABEL_OWN_CODE', 'LABEL_OWN_CODE'),
('NAME', 'NAME'),
('NAME+ARTIST', 'NAME+ARTIST'),
('NAME+AUTHOR', 'NAME+AUTHOR');


INSERT INTO right_usage_type (code, name) VALUES 
('ALL', 'All rights'),
('PUB', 'Public'),
('MOB', 'Mobile'),
('INT', 'Internet');

INSERT INTO right_category (name) values ('Author'), ('Related'), ('Author&Related');


    CREATE TABLE staging_report (
        upload_id TEXT,
        row_number TEXT,
        label_own_code TEXT,
        isrc TEXT,
        track_name TEXT,
        artist_name TEXT,
        composer TEXT,
        lyricist TEXT,
        authors TEXT,
        author_share_pct TEXT,
        related_share_pct TEXT,
        play_count TEXT,
        payout_amount TEXT,
        price_per_play TEXT,
        service_name TEXT
    
    );

CREATE INDEX idx_stg_report_isrc ON staging_report(isrc);
CREATE INDEX idx_stg_report_label_own_code ON staging_report(label_own_code);

   CREATE TABLE IF NOT EXISTS staging_report_ids (
                    id BIGSERIAL PRIMARY KEY,
                    staging_id BIGINT NOT NULL,
                    track_id BIGINT NOT NULL,
                    finding_source INT,
                    upload_id TEXT
                );




CREATE TABLE partners (
    id SERIAL PRIMARY KEY,
    organization_name VARCHAR(255) NOT NULL,
    service_name VARCHAR(255) NOT NULL,
    contract_number TEXT,
    right_usage_type_id INT NOT NULL REFERENCES right_usage_type(id), -- ССЫЛКА НА ПРАВА
    note TEXT,
    UNIQUE(organization_name, service_name)
);


CREATE TABLE report (
    id SERIAL PRIMARY KEY,
    
    -- Ссылки на справочники
    track_id INT NOT NULL REFERENCES track(id) ON DELETE CASCADE,
    partner_id INT NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
    right_category_id INT NOT NULL REFERENCES right_category(id),
    right_usage_type_id INT NOT NULL REFERENCES right_usage_type(id),
    
    -- Период
    report_month INT NOT NULL,
    report_year INT NOT NULL,
    
    -- Финансы
    play_count INT DEFAULT 0,
    payout_amount NUMERIC(20, 4) DEFAULT 0.0,
    price_per_play NUMERIC(20, 6) DEFAULT 0.0,


    -- report data source (для отладки и аудита)
    r_label_own_code varchar(30),
    r_isrc varchar(30),
    r_track_name varchar(255),
    r_artist_name varchar(255),
    r_authors varchar(512),
    r_servise_name varchar(255),
    

    finding_source  INT NOT NULL REFERENCES finding_source(id) , 
    region_id TEXT REFERENCES region(code),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для внешних ключей (критично для производительности JOIN)
CREATE INDEX idx_rf_track ON report(track_id);
CREATE INDEX idx_rf_partner ON report(partner_id);
CREATE INDEX idx_rf_right_category ON report(right_category_id);
CREATE INDEX idx_rf_usage_type ON report(right_usage_type_id);





INSERT INTO partners (organization_name, service_name, contract_number, right_usage_type_id, note)
VALUES 
('ООО Национальный Цифровой Агрегатор', 'Стриминг', '№АЛ-059/17 от 01.10.2017г.', 4, ''),
('ТОО «INTECH VAS»', 'Gudok.tele2.kz', '№ 010422/MM от 01.04.2022 г', 3, ''),
('ТОО «INTECH VAS»', 'https://funtone.kz/', '№ 010422/MM от 01.04.2022 г', 3, ''),
('ТОО «INTECH VAS»', 'https://www.simfonia.kz/', '№ 010422/MM от 01.04.2022 г', 3, ''),
('ТОО «BTS Digital»', 'Aitu', '№ PD/DGT/21-0143 от 28.09.2021 г.', 4, ''),
('INTECH VAS', 'Kcell mobi music', '№010422/ММ от 01.04.2022 г.', 4, ''),
('INTECH VAS', 'hitter', '№010422/ММ от 01.04.2022 г.', 4, 'с 01.03.26. партнер Beeline'),
('INTECH VAS', 'IZI', '№010422/ММ от 01.04.2022 г.', 4, 'с 01.03.26. партнер Beeline'),
('ЧУ «Некоммерческая организация по защите авторских и смежных прав «Аманат»', 'Сборы за публичное исполнение', '№ 01-Ал-М-2017 от 03.07.2017г.', 2, ''),
('ООО «ROZUM IT»', 'Сборы за публичное исполнение', '№ 01-01/25-1-ММ от 01.01.2025 г.', 2, ''),
('ООО «Цифровые решения»', 'Сборы за публичное исполнение', '№ 01-03/24-1-ММ от 01.03.2024 г.', 2, ''),
('Stellar Group Pty Ltd', 'Air Astana', 'Лицензионное соглашение о музыке на борту самолета от 3 декабря 2024г.', 4, '')

ON CONFLICT (organization_name, service_name) DO NOTHING;

alter table partners add column if not exists code varchar(50);


INSERT INTO label (name, composition_count, phonogram_count)
VALUES 
('ООО Первое Музыкальное Издательство (РФ)', 43162, 34103),
('ООО Национальное музыкальное Издательство (РФ)', 10043, 10528),
('ООО Эффектив Рекордс (РФ)', 4573, 3966),
('ООО Музыкальный лейбл Блэк Стар (РФ)', 812, 810),
('ООО Мейк ит Мьюзик (РФ)', 2051, 2053),
('ИП Юнусов (Каталог Тимати) (РФ)', 172, 172),
('ВК Мьюзик (РФ)', 1529, 1615),
('ООО Звук-М (РФ)', 0, 15543),
('ООО Нота (РФ)', 15543, 0),
('ООО "Блю Лайн" (Blue Sun) (РФ)', 310, 310),
('ООО "Блю Лайн" (Blue Sun) (иностр.)', 931552, 6880),
('ООО Первое Музыкальное Издательство (иностр.)', 200746, 0),
('ООО Национальное музыкальное Издательство (иностр.)', 3366096, 0),
('ООО MAESTRO (Узбекистан)', 3888, 3888),
('ООО УМИГ МЬЮЗИК (Украина)', 5660, 5471),
('ТОО BAQYT Music (KZ)', 456, 2771),
('ЧУ Аманат Организация по коллективному управлению правами (KZ)', 5523, 3242),
('Аманат Яндекс Музыка (KZ)', 4335, 4335),
('ТОО "Много Музыки"', 496, 496),
('Sony Music Entertainment (Poland)', 0, 2263734),
('ТОО «Аян Мьюзик» (KZ)', 4596947, 2359917)
ON CONFLICT (name) DO UPDATE SET 
    composition_count = EXCLUDED.composition_count,
    phonogram_count = EXCLUDED.phonogram_count;




CREATE TABLE region (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL, 
    name VARCHAR(50),
    description TEXT
);

insert into region (code, name) values 
('ALL', 'Все страны'),
('KZT, KGS, AMD,UZB', 'KZT, KGS, AMD,UZB');



CREATE OR REPLACE FUNCTION clean_and_split(text_field TEXT) 
RETURNS TEXT[] AS $$
BEGIN
    RETURN string_to_array(
        -- 1. regexp_replace заменяет все разделители на один (;)
        -- 2. btrim убирает все указанные символы (пробелы, слэши, запятые) по краям
        btrim(
            regexp_replace(text_field, '[/,:;]+', ';', 'g'), 
            ' ,/;:'
        ), 
        ';'
    );
END;
$$ LANGUAGE plpgsql;


-- ================================================================================
-- VIEW: track_full_info - Полная информация о треках с авторами и исполнителями
-- ================================================================================
CREATE OR REPLACE VIEW track_full_info AS
SELECT DISTINCT
    t.id,
    t.title,
    t.isrc,
    t.label_own_code,
    
    -- Исполнители (artist_name/performer)
    (SELECT string_agg(DISTINCT p.full_name, ', ' ORDER BY p.full_name)
     FROM track_contribution tc 
     JOIN person p ON p.id = tc.person_id
     WHERE tc.track_id = t.id AND tc.role = 'artist_name'
    ) AS artist_name,
    
    -- Композиторы
    (SELECT string_agg(DISTINCT p.full_name, ', ' ORDER BY p.full_name)
     FROM track_contribution tc 
     JOIN person p ON p.id = tc.person_id
     WHERE tc.track_id = t.id AND tc.role = 'composer'
    ) AS composer,
    
    -- Авторы текста
    (SELECT string_agg(DISTINCT p.full_name, ', ' ORDER BY p.full_name)
     FROM track_contribution tc 
     JOIN person p ON p.id = tc.person_id
     WHERE tc.track_id = t.id AND tc.role = 'lyricist'
    ) AS lyricist,
    
    -- Авторы
    (SELECT string_agg(DISTINCT p.full_name, ', ' ORDER BY p.full_name)
     FROM track_contribution tc 
     JOIN person p ON p.id = tc.person_id
     WHERE tc.track_id = t.id AND tc.role = 'authors'
    ) AS authors
    
FROM track t;





CREATE UNIQUE INDEX IF NOT EXISTS idx_label_name ON label(name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_person_name ON person(full_name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_right_holder_name ON right_holder(name);

CREATE UNIQUE INDEX IF NOT EXISTS idx_track_contribution_unique 
ON track_contribution (track_id, person_id, role);


CREATE UNIQUE INDEX IF NOT EXISTS idx_track_right_unique 
ON track_right (track_id, right_holder_id, right_category_id);




/* Временная таблица для хранения промежуточных данных при загрузке из staging_catalog*/

ALTER TABLE track_right  ADD COLUMN right_usage_type_id INTEGER REFERENCES right_usage_type(id);
ALTER TABLE right_holder ADD COLUMN label_id INTEGER REFERENCES label(id);
ALTER TABLE right_holder  ADD COLUMN effective_date DATE, ADD COLUMN termination_date DATE;


ALTER TABLE person 
    ADD COLUMN tokens TEXT[],        
    ADD COLUMN norm_key_full TEXT;    


-- Индексы, чтобы поиск на 10 млн летал:
CREATE INDEX idx_person_full_key ON person(norm_key_full);
CREATE INDEX idx_person_initial_key ON person(norm_key_initial);
CREATE INDEX idx_person_tokens_gin ON person USING GIN(tokens); -- Для сложных запросов


ALTER TABLE staging_report_agg 
    ADD COLUMN artist_name_tokens TEXT[],        
    ADD COLUMN artist_name_norm_key_full TEXT,
    ADD COLUMN authors_tokens TEXT[],
    ADD COLUMN authors_norm_key_full TEXT;

CREATE INDEX IF NOT EXISTS idx_track_title_trgm ON track USING gin (title gin_trgm_ops);
-- Ускорит поиск ролей и связку с треком
CREATE INDEX IF NOT EXISTS idx_tc_track_role ON track_contribution (track_id, role);
-- Ускорит сопоставление по нормализованному ключу
CREATE INDEX IF NOT EXISTS idx_person_norm_key ON person (norm_key_full);

-- Ускорит работу с токенами (обязательно GIN, так как это массив)
CREATE INDEX IF NOT EXISTS idx_person_tokens_gin ON person USING gin (tokens);



                CREATE TABLE IF NOT EXISTS staging_report_agg (
                id BIGSERIAL PRIMARY KEY,
                row_number int, 
                label_own_code TEXT,
                isrc TEXT,
                track_name TEXT,
                track_name_norm_key TEXT,
                track_name_tokens TEXT[],
                artist_name TEXT,
                authors TEXT,
                service_name TEXT,
                play_count BIGINT DEFAULT 0,
                payout_amount NUMERIC(20, 8) DEFAULT 0.0,
                price_per_play NUMERIC(20, 8) DEFAULT 0.0, 
                isFound BOOLEAN DEFAULT FALSE, 
                artist_name_tokens TEXT[],        
                artist_name_norm_key_full TEXT,
                authors_tokens TEXT[],
                authors_norm_key_full TEXT, 
                upload_id TEXT
            );



            




            
CREATE TABLE staging_person (
    id BIGSERIAL PRIMARY KEY,
    staging_id BIGINT,
    full_name CITEXT UNIQUE NOT NULL,
    full_name_norm_key TEXT,
    tokens TEXT[], 
    upload_id TEXT
);

-- 1. Создание таблицы
CREATE TABLE "user" (
    id SERIAL PRIMARY KEY,
    full_name CITEXT NOT NULL UNIQUE,
    login VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

-- 2. Вставка данных
-- Для Albina используем email, подходящий под домен вашей компании
INSERT INTO "user" (full_name, login, email, password_hash)
VALUES (
    'Albina Muhamedieva', 
    'albina_admin', 
    'a.muhamedieva@dyn-it.de', 
    'hash_placeholder_тут_будет_реальный_хеш'
);


ALTER TABLE staging_cataloog
   
    ADD COLUMN track_name_norm_key TEXT,
    ADD COLUMN track_name_tokens TEXT[];
 

DROP MATERIALIZED VIEW IF EXISTS public.mv_track_extended CASCADE;


CREATE MATERIALIZED VIEW mv_track_extended AS
WITH authors_flat AS (
    SELECT 
        tc.track_id,
        -- Собираем всех исполнителей и авторов через запятую без дублей
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
ORDER BY t.id;

CREATE UNIQUE INDEX idx__mv_track_extended__track_id ON mv_track_extended(track_id);

REFRESH MATERIALIZED VIEW CONCURRENTLY mv_track_extended;




CREATE TABLE report (
    id SERIAL PRIMARY KEY,
    
   
    partner_id INT NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
    right_category_id INT NOT NULL REFERENCES right_category(id),
    right_usage_type_id INT NOT NULL REFERENCES right_usage_type(id),
    
    -- Период
    report_month INT NOT NULL,
    report_year INT NOT NULL,
    
    -- Финансы
    play_count INT DEFAULT 0,
    payout_amount NUMERIC(20, 4) DEFAULT 0.0,
    price_per_play NUMERIC(20, 6) DEFAULT 0.0,



    

    upload_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



CREATE TABLE report_track_rights_cache (
    id SERIAL PRIMARY KEY,
    report_id integer,
    right_category_id integer NOT NULL,
    right_usage_type_id integer NOT NULL,
    track_id integer NOT NULL,
    right_holder_id integer NOT NULL,
    share_percentage numeric(5,2) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    staging_id integer,
    
    
    -- Определение внешних ключей (Foreign Keys)
    CONSTRAINT fk_report FOREIGN KEY (report_id) 
        REFERENCES report (id) ON DELETE CASCADE,
        
    CONSTRAINT fk_right_category FOREIGN KEY (right_category_id) 
        REFERENCES right_category (id),
        
    CONSTRAINT fk_right_usage_type FOREIGN KEY (right_usage_type_id) 
        REFERENCES right_usage_type (id),
        
    CONSTRAINT fk_track FOREIGN KEY (track_id) 
        REFERENCES track (id),
        
    CONSTRAINT fk_right_holder FOREIGN KEY (right_holder_id) 
        REFERENCES right_holder (id),
        
    CONSTRAINT fk_staging_report FOREIGN KEY (staging_id) 
        REFERENCES staging_report_agg (id) ON DELETE SET NULL
);

-- 3. Создаем индексы для ускорения поиска по внешним ключам (рекомендуется)
CREATE INDEX idx_report_track_rights_report_id ON report_track_rights_cache(report_id);
CREATE INDEX idx_report_track_rights_track_id ON  report_track_rights_cache(track_id);


insert into finding_source values(10, 'ISRC+LABEL_CODE', 'ISRC+LABEL_CODE');




CREATE MATERIALIZED VIEW mv_unified_track_rights AS
WITH base_rights AS (
    -- Агрегируем права по каждому track_id
    SELECT 
        tr.track_id,
        MAX(CASE WHEN tr.right_category_id = 2 AND tr.right_usage_type_id = 4 THEN tr.share_percentage ELSE 0 END) AS r_int,
        MAX(CASE WHEN tr.right_category_id = 2 AND tr.right_usage_type_id = 3 THEN tr.share_percentage ELSE 0 END) AS r_mob,
        MAX(CASE WHEN tr.right_category_id = 2 AND tr.right_usage_type_id = 2 THEN tr.share_percentage ELSE 0 END) AS r_pub,
        MAX(CASE WHEN tr.right_category_id = 1 AND tr.right_usage_type_id = 4 THEN tr.share_percentage ELSE 0 END) AS a_int,
        MAX(CASE WHEN tr.right_category_id = 1 AND tr.right_usage_type_id = 3 THEN tr.share_percentage ELSE 0 END) AS a_mob,
        MAX(CASE WHEN tr.right_category_id = 1 AND tr.right_usage_type_id = 2 THEN tr.share_percentage ELSE 0 END) AS a_pub
    FROM track_right tr
    GROUP BY tr.track_id
)
SELECT 
    t.track_id,
    t.label_own_code,
    CASE WHEN t.label_own_code LIKE '%-%' 
         THEN REGEXP_REPLACE(t.label_own_code, '-[A-Za-z0-9]+$', '') 
         ELSE NULL END AS base_code,
    -- Смежные права (берем только с самого трека)
    COALESCE(br.r_int, 0) AS related_int,
    COALESCE(br.r_mob, 0) AS related_mob,
    COALESCE(br.r_pub, 0) AS related_pub,
    -- Авторские права (приоритет: трек, если нет - берем сумму с альбома)
    COALESCE(br.a_int, auth_base.a_int, 0) AS author_int,
    COALESCE(br.a_mob, auth_base.a_mob, 0) AS author_mob,
    COALESCE(br.a_pub, auth_base.a_pub, 0) AS author_pub
FROM mv_track_extended t
LEFT JOIN base_rights br ON br.track_id = t.track_id
LEFT JOIN base_rights auth_base 
    ON t.label_own_code LIKE '%-%' 
    AND auth_base.track_id IN (SELECT id FROM track WHERE label_own_code = REGEXP_REPLACE(t.label_own_code, '-[A-Za-z0-9]+$', ''));

-- Индексы для мгновенной работы
CREATE UNIQUE INDEX idx_mv_unified_id ON mv_unified_track_rights(track_id);
CREATE INDEX idx_mv_unified_base ON mv_unified_track_rights(base_code);

SELECT schemaname, matviewname 
FROM pg_matviews 
WHERE schemaname = 'public';


 - 

docker exec momu_app alembic current
docker exec momu_app alembic upgrade d2b3c4e5f6a7
# 1. Первая миграция
docker exec momu_app alembic upgrade b378978c23eb

# 2. Вторая миграция
docker exec momu_app alembic upgrade c1a2b3d4e5f6

# 3. Третья миграция
docker exec momu_app alembic upgrade d2b3c4e5f6a7
