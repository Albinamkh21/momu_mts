import React, { useEffect, useState } from 'react';
import { TrackStepBasic } from './components/TrackStepBasic';
import { TrackStepRelease } from './components/TrackStepRelease';
import { TrackStepPersons } from './components/TrackStepPersons';
import { TrackStepRights } from './components/TrackStepRights';
import { createDraft, createDraftFromTrack, patchDraft, activateDraft } from './api/drafts.api';

const STEPS = [
  { label: 'Основное' },
  { label: 'Релиз' },
  { label: 'Участники' },
  { label: 'Права' },
];

/**
 * TrackWizardPage — 4-step wizard for creating or editing a track.
 * Keeps a `draftId` in state, auto-saves each step as a PATCH to the backend.
 * Final button calls the activate endpoint, which creates a new track, or —
 * when `trackId` is provided — updates the existing track in place.
 */
export function TrackWizardPage({ trackId = null, onDone, onCancel }) {
  const isEditMode = trackId != null;
  const [draftId, setDraftId] = useState(null);
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [activating, setActivating] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(null);

  // Per-step local state
  const [step1, setStep1] = useState({});
  const [step2, setStep2] = useState({});
  const [step3, setStep3] = useState({ contributors: [] });
  const [step4, setStep4] = useState({ rights: [] });

  // Create a draft on mount: an empty one for new tracks, or one pre-filled
  // from the existing track's data when editing.
  useEffect(() => {
    const init = isEditMode ? createDraftFromTrack(trackId) : createDraft();
    init
      .then((d) => {
        setDraftId(d.id);
        const payload = d.payload || {};
        if (payload.step1) setStep1(payload.step1);
        if (payload.step2) setStep2(payload.step2);
        if (payload.step3) setStep3(payload.step3);
        if (payload.step4) setStep4(payload.step4);
      })
      .catch(() =>
        setError(
          isEditMode
            ? 'Не удалось загрузить трек для редактирования.'
            : 'Не удалось создать черновик. Проверьте подключение к серверу.'
        )
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackId]);

  const stepData = [step1, step2, step3, step4];
  const stepKeys = ['step1', 'step2', 'step3', 'step4'];
  const stepSetters = [setStep1, setStep2, setStep3, setStep4];

  // Auto-save current step on leaving it.
  // Returns true on success, false on failure — callers must NOT proceed
  // (navigate / activate) when this returns false, otherwise unsaved or
  // invalid step data would be silently dropped.
  const saveCurrentStep = async () => {
    if (!draftId) return false;
    setSaving(true);
    setError('');
    try {
      await patchDraft(draftId, { [stepKeys[step]]: stepData[step] });
      return true;
    } catch (err) {
      setError('Ошибка автосохранения: ' + (err.response?.data?.detail || err.message));
      return false;
    } finally {
      setSaving(false);
    }
  };

  const goNext = async () => {
    const ok = await saveCurrentStep();
    if (!ok) return;
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const goPrev = async () => {
    const ok = await saveCurrentStep();
    if (!ok) return;
    setStep((s) => Math.max(s - 1, 0));
  };

  const handleActivate = async () => {
    const ok = await saveCurrentStep();
    if (!ok || !draftId) return;
    setActivating(true);
    setError('');
    try {
      const result = await activateDraft(draftId);
      setSuccess(result);
    } catch (err) {
      setError(
        'Ошибка активации: ' + (err.response?.data?.detail || err.message)
      );
    } finally {
      setActivating(false);
    }
  };

  // ── Success screen ────────────────────────────────────────────────────────
  if (success) {
    return (
      <div className="wizard-container">
        <div className="wizard-success">
          <h2>{isEditMode ? '✅ Трек обновлён!' : '✅ Трек создан!'}</h2>
          <p>{success.message}</p>
          <p>ID трека: <strong>{success.track_id}</strong></p>
          <button className="btn-primary" onClick={() => onDone?.(success.track_id)}>
            {isEditMode ? 'Готово' : 'Перейти к треку'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="wizard-container">
      <div className="wizard-header">
        <h2>{isEditMode ? `Редактирование трека #${trackId}` : 'Создание нового трека'}</h2>
        <button className="btn-link" onClick={onCancel}>✕ Отмена</button>
      </div>

      {/* Progress bar */}
      <div className="wizard-progress">
        {STEPS.map((s, i) => (
          <div
            key={i}
            className={`wizard-step-tab ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`}
          >
            <span className="step-number">{i + 1}</span>
            <span className="step-label">{s.label}</span>
          </div>
        ))}
      </div>

      {!draftId && !error && (
        <p style={{ padding: '1rem' }}>
          {isEditMode ? 'Загрузка данных трека...' : 'Инициализация черновика...'}
        </p>
      )}

      {error && (
        <div className="wizard-error">
          {error}
        </div>
      )}

      {/* Step content */}
      {draftId && (
        <div className="wizard-body">
          {step === 0 && <TrackStepBasic data={step1} onChange={setStep1} />}
          {step === 1 && <TrackStepRelease data={step2} onChange={setStep2} />}
          {step === 2 && <TrackStepPersons data={step3} onChange={setStep3} />}
          {step === 3 && <TrackStepRights data={step4} onChange={setStep4} />}
        </div>
      )}

      {/* Navigation */}
      <div className="wizard-footer">
        <button
          className="btn-secondary"
          onClick={goPrev}
          disabled={step === 0 || saving || activating}
        >
          ← Назад
        </button>

        <span style={{ fontSize: '0.85rem', color: '#888' }}>
          {saving ? 'Сохранение...' : `Шаг ${step + 1} из ${STEPS.length}`}
        </span>

        {step < STEPS.length - 1 ? (
          <button
            className="btn-primary"
            onClick={goNext}
            disabled={saving || !draftId}
          >
            Далее →
          </button>
        ) : (
          <button
            className="btn-primary"
            onClick={handleActivate}
            disabled={activating || saving || !draftId}
          >
            {activating
              ? (isEditMode ? 'Сохранение...' : 'Создание...')
              : (isEditMode ? '✓ Сохранить изменения' : '✓ Создать трек')}
          </button>
        )}
      </div>
    </div>
  );
}
