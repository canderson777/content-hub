(() => {
  'use strict';

  const BRAND_STORAGE_KEY = 'contentHub.activeBrand.v1';
  const BRAND_LABELS = {
    'brand-a': 'Brand A',
    brand-b: 'Brand B',
    'brand-c': 'Brand C'
  };
  const STATUS_CLASSES = {
    Draft: 'draft',
    'Needs Review': 'needs-review',
    'Changes Requested': 'changes-requested',
    Skipped: 'skipped',
    Approved: 'approved',
    Scheduled: 'scheduled',
    'Confirmed Published': 'confirmed-published'
  };
  const STATUS_OPTIONS = [
    'Draft', 'Needs Review', 'Changes Requested', 'Skipped',
    'Approved', 'Scheduled', 'Confirmed Published'
  ];
  const FORMAT_LABELS = {
    'x-post': 'X Post', 'x-thread': 'X Thread', 'x-article': 'X Article',
    'facebook-post': 'Facebook Post', 'instagram-caption': 'Instagram Caption',
    'linkedin-post': 'LinkedIn Post', 'linkedin-article': 'LinkedIn Article',
    'blog-article': 'Blog Article', 'reel-script': 'Reel Script / Caption',
    'email-draft': 'Email Draft', email: 'Email'
  };
  const activeBrandSelect = document.getElementById('activeBrandSelect');
  const assetBrandSelect = document.getElementById('assetBrandSelect');
  const approvalBody = document.getElementById('appr-body');
  const approvalStatus = document.getElementById('approvalStatus');
  const approvalsCount = document.getElementById('approvalsCount');
  const calendarRoot = document.getElementById('cal');
  const calendarTitle = document.getElementById('calendarTitle');
  const submitDialog = document.getElementById('contentSubmitDialog');
  const submitForm = document.getElementById('contentSubmitForm');
  const submitDate = document.getElementById('contentSubmitDate');
  const submitBrand = document.getElementById('contentSubmitBrand');
  const submitPreview = document.getElementById('contentSubmitPreview');
  const submitStatus = document.getElementById('contentSubmitStatus');
  const submitButton = document.getElementById('contentSubmitConfirm');

  if (!activeBrandSelect || !approvalBody || !calendarRoot || !submitDialog || !submitForm) return;

  let records = [];
  let editingRecordId = null;
  let pendingSubmission = null;
  let loadSequence = 0;
  const calendarMonth = new Date();
  calendarMonth.setDate(1);

  function setMessage(element, message, isError = false) {
    if (!element) return;
    element.textContent = message;
    element.classList.toggle('error', isError);
  }

  function brandLabel(brandId) {
    return BRAND_LABELS[brandId] || brandId;
  }

  function activeBrandId() {
    return activeBrandSelect.value;
  }

  function setBrandOptions(select, brands, selectedId) {
    if (!select) return;
    select.replaceChildren();
    brands.forEach(brand => {
      const option = document.createElement('option');
      option.value = brand.id;
      option.textContent = brand.label;
      select.append(option);
    });
    select.value = selectedId;
  }

  async function loadBrands() {
    const response = await fetch('/api/brands', {cache: 'no-store'});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Could not load configured brands.');
    const brands = (payload.brands || []).filter(brand => Object.prototype.hasOwnProperty.call(BRAND_LABELS, brand.id));
    if (!brands.length) throw new Error('No configured brands are available.');

    let savedBrand = '';
    try {
      savedBrand = localStorage.getItem(BRAND_STORAGE_KEY) || '';
    } catch (error) {
      savedBrand = '';
    }
    const currentBrand = BRAND_LABELS[activeBrandSelect.value] ? activeBrandSelect.value : '';
    const selectedId = brands.some(brand => brand.id === savedBrand)
      ? savedBrand
      : brands.some(brand => brand.id === currentBrand)
        ? currentBrand
        : brands[0].id;
    setBrandOptions(activeBrandSelect, brands, selectedId);
    setBrandOptions(assetBrandSelect, brands, selectedId);
    try {
      localStorage.setItem(BRAND_STORAGE_KEY, selectedId);
    } catch (error) {
      // The current selection still works for this page even if storage is blocked.
    }
    document.getElementById('activeBrandCaption').textContent = `Shared content records · ${brandLabel(selectedId)} · local only`;
  }

  function makeButton(label, className, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.textContent = label;
    button.addEventListener('click', onClick);
    return button;
  }

  async function postAction(record, action, fields = {}) {
    const response = await fetch(`/api/content/${encodeURIComponent(record.id)}/actions`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action, ...fields})
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Could not update this record.');
    return payload.record;
  }

  function statusClass(status) {
    return STATUS_CLASSES[status] || 'draft';
  }

  function formatLabel(format) {
    return FORMAT_LABELS[format] || format;
  }

  function addTextCell(row, text) {
    const cell = document.createElement('td');
    cell.textContent = text;
    row.append(cell);
    return cell;
  }

  function createEditorRow(record) {
    const row = document.createElement('tr');
    row.className = 'record-editor-row';
    const cell = document.createElement('td');
    cell.colSpan = 5;
    const form = document.createElement('form');
    form.className = 'record-editor';

    function field(labelText, input, full = false) {
      const wrapper = document.createElement('div');
      wrapper.className = `field${full ? ' full' : ''}`;
      const label = document.createElement('label');
      label.textContent = labelText;
      label.htmlFor = input.id;
      wrapper.append(label, input);
      return wrapper;
    }

    const title = document.createElement('input');
    title.id = `edit-title-${record.id}`;
    title.maxLength = 200;
    title.value = record.title;
    const targetDate = document.createElement('input');
    targetDate.id = `edit-date-${record.id}`;
    targetDate.type = 'date';
    targetDate.value = record.targetDate || '';
    const body = document.createElement('textarea');
    body.id = `edit-body-${record.id}`;
    body.maxLength = 20000;
    body.value = record.body;
    const note = document.createElement('textarea');
    note.id = `edit-note-${record.id}`;
    note.maxLength = 1000;
    note.value = record.reviewNote || '';
    note.placeholder = 'Optional note explaining the requested change.';
    form.append(
      field('Title', title),
      field('Calendar target date', targetDate),
      field('Draft copy', body, true),
      field('Review note', note, true)
    );
    const actions = document.createElement('div');
    actions.className = 'record-actions full';
    const feedback = document.createElement('div');
    feedback.className = 'record-status full';
    const cancel = makeButton('Cancel', 'act', () => {
      editingRecordId = null;
      renderApprovals();
    });
    const save = document.createElement('button');
    save.type = 'submit';
    save.className = 'act primary';
    save.textContent = 'Save changes';
    actions.append(cancel, save);
    form.append(actions, feedback);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      save.disabled = true;
      setMessage(feedback, 'Saving edit…');
      try {
        await postAction(record, 'edit', {
          title: title.value,
          body: body.value,
          targetDate: targetDate.value || null,
          reviewNote: note.value
        });
        editingRecordId = null;
        await loadContentRecords(`Saved. Status is Changes Requested for ${brandLabel(activeBrandId())}.`);
      } catch (error) {
        setMessage(feedback, error.message || 'Could not save the edit.', true);
        save.disabled = false;
      }
    });
    cell.append(form);
    row.append(cell);
    return row;
  }

  function createRecordRow(record) {
    const row = document.createElement('tr');
    const itemCell = document.createElement('td');
    const title = document.createElement('div');
    title.className = 'tt';
    title.textContent = record.title;
    const meta = document.createElement('div');
    meta.className = 'record-meta';
    const dateLabel = record.targetDate ? `Target ${record.targetDate}` : 'No target date';
    meta.textContent = `${record.contentType} · ${dateLabel}`;
    const details = document.createElement('details');
    details.className = 'record-copy';
    const summary = document.createElement('summary');
    summary.textContent = 'View submitted copy';
    const body = document.createElement('div');
    body.textContent = record.body;
    body.className = 'record-copy';
    details.append(summary, body);
    itemCell.append(title, meta, details);
    if (record.reviewNote) {
      const note = document.createElement('div');
      note.className = 'record-meta';
      note.textContent = `Review note: ${record.reviewNote}`;
      itemCell.append(note);
    }
    row.append(itemCell);
    addTextCell(row, record.channel);
    addTextCell(row, formatLabel(record.format));
    const statusCell = document.createElement('td');
    const status = document.createElement('span');
    status.className = `st status-${statusClass(record.status)}`;
    const dot = document.createElement('span');
    dot.className = 'dot';
    const statusText = document.createElement('span');
    statusText.className = 'status-label';
    statusText.textContent = record.status;
    status.append(dot, statusText);
    statusCell.append(status);
    row.append(statusCell);

    const actionCell = document.createElement('td');
    const actions = document.createElement('div');
    actions.className = 'record-actions';
    if (record.status === 'Needs Review') {
      actions.append(
        makeButton('Approve', 'act primary', () => runRecordAction(record, 'approve')),
        makeButton('Edit', 'act', () => { editingRecordId = record.id; renderApprovals(); }),
        makeButton('Skip', 'act', () => runRecordAction(record, 'skip'))
      );
    } else if (record.status === 'Changes Requested') {
      actions.append(
        makeButton('Edit', 'act', () => { editingRecordId = record.id; renderApprovals(); }),
        makeButton('Submit again', 'act primary', () => runRecordAction(record, 'resubmit')),
        makeButton('Skip', 'act', () => runRecordAction(record, 'skip'))
      );
    } else if (record.status === 'Approved') {
      actions.append(makeButton('Record as scheduled', 'act', () => {
        if (!window.confirm('Only record that this was scheduled elsewhere. Content Hub will not schedule it. Continue?')) return;
        runRecordAction(record, 'mark_scheduled');
      }));
    } else if (record.status === 'Scheduled') {
      actions.append(makeButton('Confirm published', 'act', () => {
        if (!window.confirm('Confirm that this content has been published outside Content Hub? This records the confirmation only.')) return;
        runRecordAction(record, 'confirm_published');
      }));
    }
    if (!actions.childElementCount) {
      const dash = document.createElement('span');
      dash.className = 'record-meta';
      dash.textContent = '—';
      actions.append(dash);
    }
    actionCell.append(actions);
    row.append(actionCell);
    return row;
  }

  async function runRecordAction(record, action) {
    setMessage(approvalStatus, `Saving ${action.replaceAll('_', ' ')}…`);
    try {
      const updated = await postAction(record, action);
      const message = action === 'approve'
        ? 'Approved. No scheduling or publishing occurred.'
        : action === 'mark_scheduled'
          ? 'Recorded as scheduled elsewhere. Content Hub did not schedule it.'
          : action === 'confirm_published'
            ? 'Recorded as confirmed published elsewhere.'
            : `${updated.status} saved.`;
      await loadContentRecords(message);
    } catch (error) {
      setMessage(approvalStatus, error.message || 'Could not update the record.', true);
    }
  }

  function renderApprovals() {
    const submittedRecords = records.filter(record => record.status !== 'Draft');
    approvalBody.replaceChildren();
    if (!submittedRecords.length) {
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 5;
      const empty = document.createElement('div');
      empty.className = 'record-empty';
      empty.textContent = `No submitted records for ${brandLabel(activeBrandId())}. Submit a copy from an editor to start this queue.`;
      cell.append(empty);
      row.append(cell);
      approvalBody.append(row);
    } else {
      submittedRecords.forEach(record => {
        approvalBody.append(createRecordRow(record));
        if (record.id === editingRecordId) approvalBody.append(createEditorRow(record));
      });
    }
    const pendingCount = records.filter(record => ['Needs Review', 'Changes Requested'].includes(record.status)).length;
    approvalsCount.textContent = String(pendingCount);
    approvalsCount.hidden = pendingCount === 0;
  }

  function renderCalendar() {
    if (!calendarRoot || !calendarTitle) return;
    const year = calendarMonth.getFullYear();
    const month = calendarMonth.getMonth();
    calendarTitle.textContent = calendarMonth.toLocaleDateString(undefined, {month: 'long', year: 'numeric'});
    calendarRoot.replaceChildren();
    ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].forEach(label => {
      const cell = document.createElement('div');
      cell.className = 'd head';
      const heading = document.createElement('div');
      heading.className = 'dh';
      heading.textContent = label;
      cell.append(heading);
      calendarRoot.append(cell);
    });
    const firstWeekday = new Date(year, month, 1).getDay();
    for (let index = 0; index < firstWeekday; index += 1) {
      const blank = document.createElement('div');
      blank.className = 'd';
      blank.setAttribute('aria-hidden', 'true');
      calendarRoot.append(blank);
    }
    const dayCount = new Date(year, month + 1, 0).getDate();
    for (let day = 1; day <= dayCount; day += 1) {
      const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const cell = document.createElement('div');
      cell.className = 'd';
      const heading = document.createElement('div');
      heading.className = 'dh';
      const dayNumber = document.createElement('b');
      dayNumber.textContent = String(day);
      heading.append(dayNumber);
      cell.append(heading);
      records.filter(record => record.targetDate === dateKey).forEach(record => {
        const event = document.createElement('div');
        event.className = `ev status-${statusClass(record.status)}`;
        event.textContent = `${record.title} · ${record.channel} · ${record.status}`;
        event.title = `${record.title} — ${record.status}`;
        cell.append(event);
      });
      calendarRoot.append(cell);
    }
    const finalWeekday = new Date(year, month, dayCount).getDay();
    for (let index = finalWeekday + 1; index < 7; index += 1) {
      const blank = document.createElement('div');
      blank.className = 'd';
      blank.setAttribute('aria-hidden', 'true');
      calendarRoot.append(blank);
    }
  }

  async function loadContentRecords(message = '') {
    const sequence = ++loadSequence;
    const brandId = activeBrandId();
    try {
      const response = await fetch(`/api/content?brand=${encodeURIComponent(brandId)}`, {cache: 'no-store'});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Could not load shared content records.');
      if (sequence !== loadSequence || brandId !== activeBrandId()) return;
      records = (payload.records || []).filter(record => record.brandId === brandId && STATUS_OPTIONS.includes(record.status));
      renderApprovals();
      renderCalendar();
      setMessage(approvalStatus, message || `${records.length} shared record${records.length === 1 ? '' : 's'} for ${brandLabel(brandId)}.`, false);
    } catch (error) {
      if (sequence !== loadSequence) return;
      records = [];
      renderApprovals();
      renderCalendar();
      setMessage(approvalStatus, error.message || 'Shared content service unavailable.', true);
    }
  }

  function submitDraft(draft) {
    if (!draft || typeof draft !== 'object') return;
    const body = typeof draft.body === 'string' ? draft.body : '';
    if (!body.trim()) {
      setMessage(approvalStatus, 'Add draft copy before submitting it for review.', true);
      return;
    }
    pendingSubmission = {
      title: typeof draft.title === 'string' && draft.title.trim() ? draft.title.trim() : 'Untitled draft',
      contentType: draft.contentType || 'social',
      channel: draft.channel || 'other',
      format: draft.format || 'other',
      body,
      brief: typeof draft.brief === 'string' ? draft.brief : '',
      sourceUrl: typeof draft.sourceUrl === 'string' ? draft.sourceUrl : '',
      sourceModule: typeof draft.sourceModule === 'string' ? draft.sourceModule : '',
      sourceId: typeof draft.sourceId === 'string' ? draft.sourceId : ''
    };
    submitBrand.textContent = brandLabel(activeBrandId());
    submitDate.value = '';
    submitPreview.textContent = body;
    setMessage(submitStatus, 'This creates a new review record; it does not move or alter the local draft.');
    submitDialog.showModal();
  }

  submitForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (!pendingSubmission) return;
    submitButton.disabled = true;
    setMessage(submitStatus, 'Saving a copy to the local review queue…');
    try {
      const response = await fetch('/api/content', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          ...pendingSubmission,
          brandId: activeBrandId(),
          targetDate: submitDate.value || null
        })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Could not submit the draft copy.');
      const submittedBrand = payload.record.brandId;
      pendingSubmission = null;
      submitDialog.close();
      await loadContentRecords(`Submitted a copy for ${brandLabel(submittedBrand)}. The local draft remains unchanged.`);
    } catch (error) {
      setMessage(submitStatus, error.message || 'Could not submit the draft copy.', true);
    } finally {
      submitButton.disabled = false;
    }
  });
  document.getElementById('contentSubmitCancel')?.addEventListener('click', () => {
    pendingSubmission = null;
    submitDialog.close();
  });
  submitDialog.addEventListener('close', () => { pendingSubmission = null; });
  document.getElementById('calendarPrev')?.addEventListener('click', () => {
    calendarMonth.setMonth(calendarMonth.getMonth() - 1);
    renderCalendar();
  });
  document.getElementById('calendarNext')?.addEventListener('click', () => {
    calendarMonth.setMonth(calendarMonth.getMonth() + 1);
    renderCalendar();
  });
  activeBrandSelect.addEventListener('change', async () => {
    const brandId = activeBrandId();
    try {
      localStorage.setItem(BRAND_STORAGE_KEY, brandId);
    } catch (error) {
      setMessage(approvalStatus, 'Brand changed for this page, but browser storage is unavailable.', true);
    }
    document.getElementById('activeBrandCaption').textContent = `Shared content records · ${brandLabel(brandId)} · local only`;
    if (assetBrandSelect && assetBrandSelect.value !== brandId) {
      assetBrandSelect.value = brandId;
      assetBrandSelect.dispatchEvent(new Event('change', {bubbles: true}));
    }
    await loadContentRecords();
  });

  window.ContentHub = {
    submitDraft,
    refresh: loadContentRecords,
    getActiveBrand: activeBrandId
  };
  renderCalendar();
  loadBrands()
    .then(async () => {
      window.BrandProfiles?.load();
      await loadContentRecords();
      await window.ChannelEditors?.refresh();
    })
    .catch(error => setMessage(approvalStatus, error.message || 'Could not initialize the brand-scoped content workspace.', true));
})();
