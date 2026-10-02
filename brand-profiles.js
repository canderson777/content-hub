(() => {
  'use strict';

  const activeBrandSelect = document.getElementById('activeBrandSelect');
  const form = document.getElementById('brandProfileForm');
  const status = document.getElementById('brandProfileStatus');
  const sourceFiles = document.getElementById('brandProfileSourceFiles');
  const brandLabel = document.getElementById('brandProfileBrandLabel');
  const resetButton = document.getElementById('resetBrandProfile');
  const saveButton = form?.querySelector('button[type="submit"]');
  const fieldControls = {
    voiceStyle: document.getElementById('brandProfileVoiceStyle'),
    audience: document.getElementById('brandProfileAudience'),
    offerAndLinks: document.getElementById('brandProfileOfferAndLinks'),
    ctaStyle: document.getElementById('brandProfileCtaStyle'),
    neverUse: document.getElementById('brandProfileNeverUse'),
    contentPillars: document.getElementById('brandProfileContentPillars'),
    positioning: document.getElementById('brandProfilePositioning')
  };

  if (!activeBrandSelect || !form || !status || !sourceFiles || !resetButton) return;

  if (saveButton) saveButton.disabled = true;
  resetButton.disabled = true;
  let requestSequence = 0;
  let currentProfile = null;
  let saving = false;
  const unsavedByBrand = new Map();

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.classList.toggle('error', isError);
  }

  function getFields() {
    return Object.fromEntries(
      Object.entries(fieldControls).map(([key, control]) => [key, control.value])
    );
  }

  function setFields(fields) {
    Object.entries(fieldControls).forEach(([key, control]) => {
      control.value = typeof fields?.[key] === 'string' ? fields[key] : '';
    });
  }

  function setBusy(value) {
    saving = value;
    Object.values(fieldControls).forEach(control => { control.disabled = value; });
    saveButton.disabled = value;
    resetButton.disabled = value || !currentProfile?.isCustomized;
  }

  function updateProfile(profile) {
    currentProfile = profile;
    saveButton.disabled = saving;
    brandLabel.textContent = profile.label;
    const unsaved = unsavedByBrand.get(profile.brandId);
    if (unsaved) {
      setFields(unsaved);
      setStatus(`Unsaved edits for ${profile.label}. Save to keep them in this Content Hub.`);
    } else {
      setFields(profile.fields);
      const state = profile.isCustomized
        ? `Content Hub-only profile override saved ${profile.updatedAt || 'locally'}.`
        : 'Loaded from the current Marketing Agent OS source profile.';
      setStatus(profile.sourceStatus === 'incomplete'
        ? `${state} Missing source files: ${(profile.missingFiles || []).join(', ')}.`
        : state);
    }

    const sourceList = (profile.sourceFiles || []).map(path => `brands/${profile.brandId}/${path}`);
    const sourceText = sourceList.length ? `Source files: ${sourceList.join(' · ')}` : 'No profile source documents found for this brand.';
    const modifiedText = profile.sourceUpdatedAt ? ` · source updated ${profile.sourceUpdatedAt}` : '';
    sourceFiles.textContent = `${sourceText}${modifiedText}`;
    resetButton.disabled = saving || !profile.isCustomized;
  }

  async function readResponse(response) {
    const contentType = response.headers.get('Content-Type') || '';
    if (contentType.includes('application/json')) return response.json();
    const text = await response.text();
    throw new Error(text || `Profile request failed (${response.status}).`);
  }

  async function load() {
    const brandId = activeBrandSelect.value;
    if (!brandId) return;
    const sequence = ++requestSequence;
    setStatus(`Loading ${brandId} profile…`);
    try {
      const response = await fetch(`/api/brand-profile?brand=${encodeURIComponent(brandId)}`, {cache: 'no-store'});
      const payload = await readResponse(response);
      if (!response.ok) throw new Error(payload.error || 'Could not load this brand profile.');
      if (sequence !== requestSequence || brandId !== activeBrandSelect.value) return;
      if (payload.profile?.brandId !== brandId || !payload.profile.fields) {
        throw new Error('The profile service returned a different brand or an incomplete profile.');
      }
      updateProfile(payload.profile);
    } catch (error) {
      if (sequence !== requestSequence || brandId !== activeBrandSelect.value) return;
      currentProfile = null;
      brandLabel.textContent = brandId;
      setFields(unsavedByBrand.get(brandId) || {});
      sourceFiles.textContent = 'Profile source unavailable. Check the local Content Hub server and configured brand folder.';
      setStatus(error.message || 'Could not load the selected brand profile.', true);
      resetButton.disabled = true;
    }
  }

  form.addEventListener('input', () => {
    if (!currentProfile || currentProfile.brandId !== activeBrandSelect.value) return;
    unsavedByBrand.set(currentProfile.brandId, getFields());
    setStatus(`Unsaved edits for ${currentProfile.label}. Save to keep them in this Content Hub.`);
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (saving || !currentProfile) return;
    const brandId = currentProfile.brandId;
    const fields = getFields();
    setBusy(true);
    setStatus(`Saving ${currentProfile.label} profile to local Content Hub storage…`);
    try {
      const response = await fetch(`/api/brand-profile?brand=${encodeURIComponent(brandId)}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({fields})
      });
      const payload = await readResponse(response);
      if (!response.ok) throw new Error(payload.error || 'Could not save this brand profile.');
      unsavedByBrand.delete(brandId);
      if (activeBrandSelect.value === brandId) {
        updateProfile(payload.profile);
        setStatus(`Saved ${payload.profile.label} as a Content Hub-only profile override. Source Markdown files are unchanged.`);
      }
    } catch (error) {
      setStatus(error.message || 'Could not save this brand profile.', true);
    } finally {
      setBusy(false);
    }
  });

  resetButton.addEventListener('click', async () => {
    if (saving || !currentProfile?.isCustomized) return;
    const brandId = currentProfile.brandId;
    if (!window.confirm(`Reset ${currentProfile.label} to the current source profile? This removes only the Content Hub override.`)) return;
    setBusy(true);
    setStatus(`Reloading ${currentProfile.label} from the source profile…`);
    try {
      const response = await fetch(`/api/brand-profile?brand=${encodeURIComponent(brandId)}`, {method: 'DELETE'});
      const payload = await readResponse(response);
      if (!response.ok) throw new Error(payload.error || 'Could not reset this brand profile.');
      unsavedByBrand.delete(brandId);
      if (activeBrandSelect.value === brandId) {
        updateProfile(payload.profile);
        setStatus(`Reset ${payload.profile.label} to its current source profile. Source Markdown files were not changed.`);
      }
    } catch (error) {
      setStatus(error.message || 'Could not reset this brand profile.', true);
    } finally {
      setBusy(false);
    }
  });

  activeBrandSelect.addEventListener('change', load);
  window.BrandProfiles = {load};
  load();
})();
