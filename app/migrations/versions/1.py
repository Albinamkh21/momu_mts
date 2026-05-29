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

