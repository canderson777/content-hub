(() => {
  'use strict';

  const STORAGE_KEY = 'contentHub.localOrganizers.v1';
  const VALID_DAYS = new Set([2, 3, 7]);
  const X_FORMATS = new Set(['post', 'thread', 'article']);
  const platformConfig = {
    facebook: {label: 'Facebook', format: 'facebook-post'},
    instagram: {label: 'Instagram', format: 'instagram-caption'},
    linkedin: {label: 'LinkedIn', format: 'linkedin-post'},
    x: {label: 'X'},
    blog: {label: 'Blog', format: 'blog-article'},
    email: {label: 'Email', format: 'email'}
  };
  const formatConfig = {
    'x-post': {label: 'X Post', limit: 280, help: 'One post; 280 characters maximum.'},
    'x-thread': {label: 'X Thread', perPostLimit: 280, help: 'Separate posts with a blank line; each post should be 280 characters or less.'},
    'x-article': {label: 'X Article', help: 'Long-form draft; the X Post character cap does not apply.'},
    'facebook-post': {label: 'Facebook Post', help: 'Editable Facebook post draft.'},
    'instagram-caption': {label: 'Instagram Caption', limit: 2200, help: 'Instagram caption guide: 2,200 characters.'},
    'linkedin-post': {label: 'LinkedIn Post', limit: 3000, help: 'LinkedIn post guide: 3,000 characters.'},
    'linkedin-article': {label: 'LinkedIn Article', help: 'Long-form editable article draft.'},
    'blog-article': {label: 'Blog Article', help: 'Long-form editable blog draft.'},
    email: {label: 'Email', help: 'Editable email draft.'}
  };

  const multiDayForm = document.getElementById('multiDayPackForm');
  const repurposeForm = document.getElementById('repurposeForm');
  if (!multiDayForm || !repurposeForm) return;

  const multiDayStatus = document.getElementById('multiDayPackStatus');
  const repurposeStatus = document.getElementById('repurposeStatus');
  const multiDayOutputs = document.getElementById('multiDayPackOutputs');
  const repurposeOutputs = document.getElementById('repurposeDraftOutputs');
  const multiDayPlatformInputs = Array.from(document.querySelectorAll('input[name="multiDayPlatform"]'));
  const repurposeSourceText = document.getElementById('repurposeSourceText');
  const repurposeSourceUrl = document.getElementById('repurposeSourceUrl');
  const repurposeFormatInput = document.getElementById('repurposeFormat');

  function makeId(prefix) {
    return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
  }

  function asText(value, maxLength) {
    return typeof value === 'string' ? value.slice(0, maxLength) : '';
  }

  function setStatus(element, message, isError = false) {
    if (!element) return;
    element.textContent = message;
    element.classList.toggle('error', isError);
  }

  function emptyState() {
    return {packs: [], repurposeDrafts: []};
  }

  function normalizePack(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
    const days = Number(raw.days);
    if (!VALID_DAYS.has(days)) return null;
    const platforms = Array.isArray(raw.platforms)
      ? [...new Set(raw.platforms.filter(platform => Object.prototype.hasOwnProperty.call(platformConfig, platform)))]
      : [];
    const xFormat = X_FORMATS.has(raw.xFormat) ? raw.xFormat : 'post';
    const assets = Array.isArray(raw.assets) ? raw.assets.slice(0, 42).map(asset => {
      if (!asset || typeof asset !== 'object' || Array.isArray(asset)) return null;
      const platform = asset.platform;
      if (!Object.prototype.hasOwnProperty.call(platformConfig, platform)) return null;
      const day = Number(asset.day);
      if (!Number.isInteger(day) || day < 1 || day > days) return null;
      const expectedFormat = platform === 'x' ? `x-${xFormat}` : platformConfig[platform].format;
      if (asset.format !== expectedFormat || !formatConfig[expectedFormat]) return null;
      return {
        id: asText(asset.id, 100) || makeId('asset'),
        day,
        platform,
        format: expectedFormat,
        angle: asText(asset.angle, 120),
        text: asText(asset.text, 20000)
      };
    }).filter(Boolean) : [];
    return {
      id: asText(raw.id, 100) || makeId('pack'),
      title: asText(raw.title, 80) || 'Multi-day Pack',
      brief: asText(raw.brief, 2000),
      days,
      platforms,
      xFormat,
      createdAt: asText(raw.createdAt, 80),
      status: 'Draft',
      assets
    };
  }

  function normalizeRepurposeDraft(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
    if (!Object.prototype.hasOwnProperty.call(formatConfig, raw.format)) return null;
    return {
      id: asText(raw.id, 100) || makeId('repurpose'),
      format: raw.format,
      sourceText: asText(raw.sourceText, 20000),
      sourceUrl: asText(raw.sourceUrl, 2000),
      text: asText(raw.text, 20000),
      createdAt: asText(raw.createdAt, 80),
      status: 'Draft'
    };
  }

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return emptyState();
      return {
        packs: Array.isArray(saved.packs) ? saved.packs.map(normalizePack).filter(Boolean).slice(0, 30) : [],
        repurposeDrafts: Array.isArray(saved.repurposeDrafts)
          ? saved.repurposeDrafts.map(normalizeRepurposeDraft).filter(Boolean).slice(0, 100)
          : []
      };
    } catch (error) {
      return emptyState();
    }
  }

  const state = loadState();

  function saveState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      return true;
    } catch (error) {
      return false;
    }
  }

  function formatMeta(format, text) {
    const config = formatConfig[format] || {};
    if (config.perPostLimit) {
      const posts = text.split(/\n\s*\n/).filter(post => post.trim());
      const overLimit = posts.filter(post => post.length > config.perPostLimit).length;
      const message = overLimit
        ? `${posts.length} posts · ${overLimit} over ${config.perPostLimit} characters`
        : `${posts.length} posts · ${config.perPostLimit} characters max per post`;
      return {text: message, overLimit: overLimit > 0};
    }
    const limit = config.limit || null;
    return {
      text: limit ? `${text.length} / ${limit} characters` : `${text.length} characters`,
      overLimit: !!limit && text.length > limit
    };
  }

  function makeEmptyMessage(text) {
    const empty = document.createElement('div');
    empty.className = 'organizer-empty';
    empty.textContent = text;
    return empty;
  }

  function makeLabel(text, control) {
    const label = document.createElement('label');
    label.htmlFor = control.id;
    label.textContent = text;
    return label;
  }

  function makeDraftEditor({id, labelText, value, format, rows = 5, placeholder, onInput}) {
    const field = document.createElement('div');
    field.className = 'field';
    const textarea = document.createElement('textarea');
    textarea.id = id;
    textarea.rows = rows;
    textarea.maxLength = 20000;
    textarea.value = value;
    textarea.placeholder = placeholder;
    const label = makeLabel(labelText, textarea);
    const counter = document.createElement('div');
    counter.className = 'organizer-counter';
    const help = document.createElement('div');
    help.className = 'organizer-format-help';
    help.textContent = formatConfig[format]?.help || '';

    function updateCounter() {
      const meta = formatMeta(format, textarea.value);
      counter.textContent = meta.text;
      counter.classList.toggle('over-limit', meta.overLimit);
    }

    textarea.addEventListener('input', () => {
      onInput(textarea.value);
      updateCounter();
    });
    updateCounter();
    field.append(label, textarea, counter, help);
    return field;
  }

  function makeSubmitButton(getDraft, statusElement) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'act primary organizer-submit';
    button.textContent = 'Submit for review';
    button.addEventListener('click', () => {
      if (!window.ContentHub || typeof window.ContentHub.submitDraft !== 'function') {
        setStatus(statusElement, 'The shared content service is not ready. Refresh the page and retry.', true);
        return;
      }
      window.ContentHub.submitDraft(getDraft());
    });
    return button;
  }

  function makeDeleteButton(label, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'organizer-delete';
    button.textContent = 'Delete';
    button.setAttribute('aria-label', label);
    button.addEventListener('click', onClick);
    return button;
  }

  function renderPackAsset(pack, asset) {
    const card = document.createElement('article');
    card.className = 'organizer-asset';
    const heading = document.createElement('div');
    heading.className = 'organizer-asset-head';
    const title = document.createElement('strong');
    title.textContent = `Day ${asset.day} · ${formatConfig[asset.format].label}`;
    const status = document.createElement('span');
    status.className = 'tag';
    status.textContent = 'Draft';
    heading.append(title, status);

    const angleField = document.createElement('div');
    angleField.className = 'field';
    const angle = document.createElement('input');
    angle.id = `${asset.id}-angle`;
    angle.type = 'text';
    angle.maxLength = 120;
    angle.value = asset.angle;
    angle.placeholder = `Add a distinct angle or hook for Day ${asset.day}`;
    angleField.append(makeLabel('Angle / hook', angle), angle);
    angle.addEventListener('input', () => {
      asset.angle = angle.value;
      if (!saveState()) setStatus(multiDayStatus, 'Browser storage is unavailable; this edit may not persist after closing the page.', true);
    });

    const bodyPlaceholder = asset.format === 'x-thread'
      ? 'Write the thread; separate individual posts with a blank line.'
      : asset.format === 'x-post'
        ? 'Write one X post (280 characters maximum).'
        : 'Write or paste this day’s draft copy.';
    const bodyField = makeDraftEditor({
      id: `${asset.id}-copy`,
      labelText: asset.format === 'x-thread' ? 'Thread copy' : 'Draft copy',
      value: asset.text,
      format: asset.format,
      rows: 4,
      placeholder: bodyPlaceholder,
      onInput: text => {
        asset.text = text;
        if (!saveState()) setStatus(multiDayStatus, 'Browser storage is unavailable; this edit may not persist after closing the page.', true);
      }
    });
    const submit = makeSubmitButton(() => ({
      title: `${pack.title} · Day ${asset.day} · ${formatConfig[asset.format].label}`,
      contentType: asset.format === 'blog-article' ? 'blog' : asset.format === 'email' ? 'email' : 'social',
      channel: asset.platform,
      format: asset.format,
      body: asset.text,
      brief: `${pack.brief}${asset.angle ? `\n\nAngle: ${asset.angle}` : ''}`,
      sourceModule: 'multi-day-pack',
      sourceId: `${pack.id}:${asset.id}`
    }), multiDayStatus);
    card.append(heading, angleField, bodyField, submit);
    return card;
  }

  function renderPacks() {
    multiDayOutputs.replaceChildren();
    if (!state.packs.length) {
      multiDayOutputs.append(makeEmptyMessage('No local packs yet. Create one to start planning.'));
      return;
    }
    state.packs.forEach(pack => {
      const card = document.createElement('article');
      card.className = 'organizer-card';
      const heading = document.createElement('div');
      heading.className = 'organizer-card-head';
      const titleBlock = document.createElement('div');
      const title = document.createElement('h3');
      title.textContent = pack.title;
      const metadata = document.createElement('div');
      metadata.className = 'organizer-card-meta';
      metadata.textContent = `${pack.days} days · ${pack.assets.length} editable Draft slots`;
      titleBlock.append(title, metadata);
      const badge = document.createElement('span');
      badge.className = 'tag';
      badge.textContent = 'Draft';
      const remove = makeDeleteButton(`Delete ${pack.title}`, () => {
        if (!window.confirm(`Delete the local pack “${pack.title}” and its draft slots?`)) return;
        state.packs = state.packs.filter(item => item.id !== pack.id);
        const saved = saveState();
        renderPacks();
        setStatus(multiDayStatus, saved ? 'Local pack deleted.' : 'Pack removed from this view, but browser storage could not be updated.', !saved);
      });
      heading.append(titleBlock, badge, remove);
      const brief = document.createElement('div');
      brief.className = 'organizer-brief';
      brief.textContent = `Anchor brief · ${pack.brief}`;
      const count = document.createElement('div');
      count.className = 'organizer-assets-count';
      count.textContent = `One editable asset per selected destination per day · ${pack.platforms.map(platform => platformConfig[platform].label).join(', ')}`;
      const assets = document.createElement('div');
      assets.className = 'organizer-assets';
      pack.assets.forEach(asset => assets.append(renderPackAsset(pack, asset)));
      card.append(heading, brief, count, assets);
      multiDayOutputs.append(card);
    });
  }

  multiDayForm.addEventListener('submit', event => {
    event.preventDefault();
    const titleInput = document.getElementById('multiDayPackTitle');
    const briefInput = document.getElementById('multiDayPackBrief');
    const days = Number(document.getElementById('multiDayDays').value);
    const xFormat = document.getElementById('multiDayXFormat').value;
    const brief = briefInput.value;
    const platforms = multiDayPlatformInputs.filter(input => input.checked).map(input => input.value);

    if (!brief.trim()) {
      setStatus(multiDayStatus, 'Add an anchor brief before creating a pack.', true);
      briefInput.focus();
      return;
    }
    if (!VALID_DAYS.has(days)) {
      setStatus(multiDayStatus, 'Choose a pack length of 2, 3, or 7 days.', true);
      return;
    }
    if (!platforms.length) {
      setStatus(multiDayStatus, 'Choose at least one destination for the pack.', true);
      return;
    }
    if (!X_FORMATS.has(xFormat)) {
      setStatus(multiDayStatus, 'Choose an X format before creating the pack.', true);
      return;
    }

    const assets = [];
    for (let day = 1; day <= days; day += 1) {
      platforms.forEach(platform => {
        const format = platform === 'x' ? `x-${xFormat}` : platformConfig[platform].format;
        assets.push({id: makeId('asset'), day, platform, format, angle: '', text: ''});
      });
    }
    const pack = {
      id: makeId('pack'),
      title: titleInput.value.trim() || 'Multi-day Pack',
      brief,
      days,
      platforms,
      xFormat,
      createdAt: new Date().toISOString(),
      status: 'Draft',
      assets
    };
    state.packs.unshift(pack);
    const saved = saveState();
    renderPacks();
    setStatus(
      multiDayStatus,
      saved
        ? `Created a ${days}-day local pack with ${assets.length} editable Draft slots. Saved in this browser; nothing was published.`
        : 'Pack created for this session, but browser storage is unavailable and it may not persist after closing the page.',
      !saved
    );
  });

  function renderRepurposeDraft(draft) {
    const card = document.createElement('article');
    card.className = 'organizer-card';
    const heading = document.createElement('div');
    heading.className = 'organizer-card-head';
    const titleBlock = document.createElement('div');
    const title = document.createElement('h3');
    title.textContent = formatConfig[draft.format].label;
    const metadata = document.createElement('div');
    metadata.className = 'organizer-card-meta';
    metadata.textContent = 'Local editable copy · Draft';
    titleBlock.append(title, metadata);
    const badge = document.createElement('span');
    badge.className = 'tag';
    badge.textContent = 'Draft';
    const remove = makeDeleteButton(`Delete ${formatConfig[draft.format].label} draft`, () => {
      if (!window.confirm(`Delete this local ${formatConfig[draft.format].label} draft?`)) return;
      state.repurposeDrafts = state.repurposeDrafts.filter(item => item.id !== draft.id);
      const saved = saveState();
      renderRepurposeDrafts();
      setStatus(repurposeStatus, saved ? 'Local repurpose draft deleted.' : 'Draft removed from this view, but browser storage could not be updated.', !saved);
    });
    heading.append(titleBlock, badge, remove);

    const reference = document.createElement('div');
    reference.className = 'organizer-reference';
    reference.textContent = draft.sourceUrl ? `Reference only · URL not fetched: ${draft.sourceUrl}` : 'Source text copied as-is; no source URL attached.';
    const editor = makeDraftEditor({
      id: `${draft.id}-copy`,
      labelText: 'Editable draft copy',
      value: draft.text,
      format: draft.format,
      rows: 6,
      placeholder: 'Edit this local working copy into the selected format.',
      onInput: text => {
        draft.text = text;
        if (!saveState()) setStatus(repurposeStatus, 'Browser storage is unavailable; this edit may not persist after closing the page.', true);
      }
    });
    const channelByFormat = {
      'x-post': 'x', 'x-thread': 'x', 'x-article': 'x',
      'facebook-post': 'facebook', 'instagram-caption': 'instagram',
      'linkedin-post': 'linkedin', 'linkedin-article': 'linkedin',
      'blog-article': 'blog', email: 'email'
    };
    const submit = makeSubmitButton(() => ({
      title: `${formatConfig[draft.format].label} draft`,
      contentType: draft.format === 'blog-article' ? 'blog' : draft.format === 'email' ? 'email' : 'social',
      channel: channelByFormat[draft.format],
      format: draft.format,
      body: draft.text,
      brief: draft.sourceText.slice(0, 2000),
      sourceUrl: draft.sourceUrl,
      sourceModule: 'repurpose',
      sourceId: draft.id
    }), repurposeStatus);
    card.append(heading, reference, editor, submit);
    return card;
  }

  function renderRepurposeDrafts() {
    repurposeOutputs.replaceChildren();
    if (!state.repurposeDrafts.length) {
      repurposeOutputs.append(makeEmptyMessage('No local repurpose drafts yet. Paste source text and choose a format.'));
      return;
    }
    state.repurposeDrafts.forEach(draft => repurposeOutputs.append(renderRepurposeDraft(draft)));
  }

  repurposeForm.addEventListener('submit', event => {
    event.preventDefault();
    const sourceText = repurposeSourceText.value;
    const sourceUrl = repurposeSourceUrl.value.trim();
    const format = repurposeFormatInput.value;
    if (!sourceText.trim()) {
      setStatus(repurposeStatus, 'Paste source text before creating a repurpose draft.', true);
      repurposeSourceText.focus();
      return;
    }
    let validReferenceUrl = true;
    if (sourceUrl) {
      try {
        const reference = new URL(sourceUrl);
        validReferenceUrl = ['http:', 'https:'].includes(reference.protocol) && !!reference.hostname && repurposeSourceUrl.checkValidity();
      } catch (error) {
        validReferenceUrl = false;
      }
    }
    if (!validReferenceUrl) {
      setStatus(repurposeStatus, 'Enter a valid http:// or https:// reference URL, or leave the URL blank.', true);
      repurposeSourceUrl.focus();
      return;
    }
    if (!Object.prototype.hasOwnProperty.call(formatConfig, format)) {
      setStatus(repurposeStatus, 'Choose a supported output format.', true);
      return;
    }
    const draft = {
      id: makeId('repurpose'),
      format,
      sourceText,
      sourceUrl,
      text: sourceText,
      createdAt: new Date().toISOString(),
      status: 'Draft'
    };
    state.repurposeDrafts.unshift(draft);
    const saved = saveState();
    renderRepurposeDrafts();
    setStatus(
      repurposeStatus,
      saved
        ? `Created an editable ${formatConfig[format].label} copy from the source text. It was not rewritten or published.`
        : 'Draft created for this session, but browser storage is unavailable and it may not persist after closing the page.',
      !saved
    );
  });

  renderPacks();
  renderRepurposeDrafts();
})();
