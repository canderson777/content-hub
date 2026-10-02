(() => {
  'use strict';

  const BRAND_LABELS = {
    'brand-a': 'Brand A',
    brand-b: 'Brand B',
    'brand-c': 'Brand C'
  };
  const CONFIG = {
    blog: {
      label: 'Blog',
      formId: 'blogEditorForm',
      listId: 'blogContentRecords',
      statusId: 'blogEditorStatus',
      titleLabel: 'Article title',
      briefLabel: 'Reader problem / angle',
      bodyLabel: 'Article draft',
      contentType: 'blog',
      channel: 'blog',
      format: 'blog-article',
      handoffTitle: 'Blog CMS handoff'
    },
    reels: {
      label: 'Reels',
      formId: 'reelsEditorForm',
      listId: 'reelsContentRecords',
      statusId: 'reelsEditorStatus',
      titleLabel: 'Reel working title',
      briefLabel: 'Hook / direction',
      bodyLabel: 'Script, caption, or shot notes',
      contentType: 'reel',
      channel: 'reels',
      format: 'reel-script',
      handoffTitle: 'Reel production handoff'
    },
    email: {
      label: 'Email',
      formId: 'emailEditorForm',
      listId: 'emailContentRecords',
      statusId: 'emailEditorStatus',
      titleLabel: 'Subject line',
      briefLabel: 'Audience / CTA angle',
      bodyLabel: 'Email body',
      contentType: 'email',
      channel: 'email',
      format: 'email-draft',
      handoffTitle: 'Email copy handoff'
    }
  };

  const TEMPLATES = {
    blog: {
      'case-study': {
        title: 'How [Client/Business] Solved [Specific Problem] in [Timeframe]',
        brief: 'Target audience: Business owners facing [Pain Point]. Goal: Show the exact breakdown of how we fixed it and the measurable outcome.',
        body: `## The Problem\nDescribe the exact situation before the solution. What was broken, leaking money, or costing too much time?\n\n## What Failed First\nList 1 or 2 common fixes they tried that didn't work (and why).\n\n## The Direct Solution\n1. Step 1: Exactly what was changed.\n2. Step 2: The tool or process introduced.\n3. Step 3: How it was verified.\n\n## The Outcome\n- Result 1 (metric, time saved, or revenue)\n- Result 2 (peace of mind or clarity)\n\n## Key Takeaway & Next Step\nSummarize the main lesson. Add one clear CTA with your booking link or resource.`
      },
      'myth-vs-reality': {
        title: 'Why Most [Industry] Advice About [Topic] Is Wrong',
        brief: 'Target audience: People struggling with standard advice. Goal: Debunk an outdated habit and replace it with a pragmatic alternative.',
        body: `## The Conventional Myth\n"Everyone tells you to do [Myth]. Here is why that advice is outdated or hurting your results."\n\n## The Real-World Reality\nExplain the hidden cost or downside of the conventional method.\n\n## What Smart Operators Do Instead\nProvide the pragmatic alternative with 2 or 3 concrete points:\n- Rule 1:\n- Rule 2:\n- Rule 3:\n\n## Action Checklist\nWhat should the reader do today? Keep it simple.\n\n## Next Step\nInvite them to try the new method or reach out for guidance.`
      },
      'buyer-guide': {
        title: '5 Questions to Ask Before Hiring a [Service/Provider] in [Year]',
        brief: 'Target audience: Buyers comparing options. Goal: Position our expertise by showing what mistakes to watch for.',
        body: `## Introduction\nFinding the right partner for [Service] is hard. Ask these 5 questions before signing anything.\n\n1. **Question 1: [Critical Requirement]?**\n   What they should say vs. the red flag answer.\n\n2. **Question 2: [Scope & Timeline]?**\n   How to prevent surprise delays.\n\n3. **Question 3: [Proof of Work / Verification]?**\n   How real results are audited.\n\n4. **Question 4: [Pricing & Ownership]?**\n   Who owns the accounts and deliverables.\n\n5. **Question 5: [Support & Hand-off]?**\n   What happens after launch.\n\n## Summary & Decision Matrix\nBrief wrap-up. Add a CTA to review their current setup or audit.`
      },
      'tool-framework': {
        title: 'The [Name] Framework: A Practical Checklist for [Task]',
        brief: 'Target audience: Operators who want a repeatable standard. Goal: High utility reference guide they save and share.',
        body: `## Why This Matters\nEvery business loses time when [Task] is handled ad-hoc. Here is our exact step-by-step framework.\n\n### Phase 1: Audit & Baseline\n- Item 1\n- Item 2\n\n### Phase 2: Implementation\n- Item 1\n- Item 2\n\n### Phase 3: Verification & Routine\n- Item 1\n- Item 2\n\n## Deliverable Template\nProvide a fill-in-the-blank snippet or resource link.\n\n## Next Step\nDirect call to action.`
      }
    },
    reels: {
      '3-part-reel': {
        title: '3-Part Reel: [Topic] Fix in 45 Seconds',
        brief: 'Hook: Stop the scroll with a direct callout. Talk track: 3 fast value points. CTA: Save or comment.',
        body: `[3-SECOND HOOK - ON CAMERA / OVERLAY TEXT]:\n"Stop doing [Common Mistake] if you actually want [Desired Result] in [Industry]."\n\n[TALK TRACK / MAIN VALUE - 30 SECONDS]:\n"Here are the 3 things that actually move the needle:\n1. [Point 1 - One sentence]\n2. [Point 2 - One sentence]\n3. [Point 3 - One sentence]"\n\n[CALL TO ACTION - 5 SECONDS]:\n"Save this Reel for your next sprint, or comment '[KEYWORD]' and I'll send you our checklist."\n\n[CAPTION DRAFT]:\nMost people overcomplicate [Topic]. Here's the 3-step breakdown you need today.\n\n1️⃣ [Point 1]\n2️⃣ [Point 2]\n3️⃣ [Point 3]\n\nLink in bio for the complete walkthrough.`
      },
      'contrarian-truth': {
        title: 'Contrarian Truth: Stop [Bad Habit]',
        brief: 'Hook: Challenge a sacred cow. Body: Explain the hidden flaw. CTA: Ask for their view in comments.',
        body: `[3-SECOND HOOK]:\n"I'm going to say what nobody in [Industry] wants to admit about [Topic]."\n\n[TALK TRACK]:\n"Everyone spends hours on [Tactic], thinking it creates growth. But here is what really happens: [The Flaw]. If you want real traction, focus on [Better Tactic] instead."\n\n[CALL TO ACTION]:\n"Agree or disagree? Drop your thoughts in the comments."\n\n[CAPTION DRAFT]:\nUnpopular opinion on [Topic]. What has been your experience? Let's discuss below.`
      },
      'faceless-screen': {
        title: 'Faceless Demo: 60-Second [Feature/Tool] Walkthrough',
        brief: 'Visual: Screen capture of dashboard or workflow. Audio: Clear voiceover or text overlay with background audio.',
        body: `[VISUAL CUE / B-ROLL]:\nScreen recording showing the exact clicks in the dashboard / app. Zoom in on key metrics or results.\n\n[TEXT ON SCREEN / VOICEOVER]:\n"Watch me [Complete Task] in under 60 seconds without [Painful Step].\nFirst, open [Tool].\nNext, toggle [Setting].\nBoom — here is the final output."\n\n[CALL TO ACTION]:\n"Comment 'LINK' and I'll send you the exact template."\n\n[CAPTION DRAFT]:\nQuick 60-second walkthrough. Save this so you don't lose the steps later!`
      },
      'before-after': {
        title: 'Before & After Transformation: [Metric/Result]',
        brief: 'Hook: High contrast between the messy start and the clean result. CTA: How we can do it for them.',
        body: `[VISUAL HOOK]:\nSplit screen or fast cut showing the chaotic 'Before' state.\n\n[TALK TRACK]:\n"This was [Situation] two weeks ago: disorganized, slow, and losing leads.\nAnd this is it today: automated, verified, and running smoothly."\n\n[CALL TO ACTION]:\n"Want us to audit your setup? Tap the link in our bio."\n\n[CAPTION DRAFT]:\nThe difference between an ad-hoc system and an automated pipeline. Drop a line if you're ready to clean up your workflow.`
      }
    },
    email: {
      'quick-value': {
        title: 'Quick 2-minute tip on [Topic]',
        brief: 'Audience: Busy subscribers. Goal: Provide one immediate actionable win with zero fluff.',
        body: `Hey [First Name],\n\nQuick thought for your week:\n\nMost businesses waste time on [Common Complication] when solving [Problem].\n\nHere is the simple shortcut we use instead:\n\n👉 [1-2 sentences explaining the tip]\n\nGive it a try on your next project and let me know if it helps.\n\nBest,\n[Your Name]`
      },
      'story-lesson': {
        title: 'What happened when we tested [Idea]',
        brief: 'Audience: Engaged contacts. Goal: Share a relatable real-life lesson leading to a soft CTA.',
        body: `Hey [First Name],\n\nSomething interesting happened earlier this week.\n\n[Brief 2-3 sentence story about a real challenge or surprise discovery].\n\nHere was the big takeaway:\n\n[Core lesson: 2 bullet points or short paragraph].\n\nIf you're dealing with something similar right now, hit reply — happy to share the notes we took.\n\nBest,\n[Your Name]`
      },
      'soft-offer': {
        title: 'Quick question about [Business Goal]?',
        brief: 'Audience: Existing prospects or warm list. Goal: Direct, low-pressure conversation starter.',
        body: `Hey [First Name],\n\nAre you still looking to improve [Specific Goal, e.g. local visibility / client follow-ups] this quarter?\n\nWe have room to take on 2 more [audits / reviews] this month.\n\nIf you'd like us to take a look at your current setup, just reply with 'YES' or check out the details here: [Link].\n\nNo pressure either way.\n\nBest,\n[Your Name]`
      },
      'curated-bullet': {
        title: 'The 3-minute brief: [Topic]',
        brief: 'Audience: Newsletter readers. Goal: Curated digest of 1 big thought + 2 practical resources.',
        body: `Hey [First Name],\n\nHere is what caught our attention this week:\n\n1. **The Big Idea**: [Summary of a key trend or strategic shift]\n2. **Tool / Resource of the Week**: [Name + link + 1 sentence why it matters]\n3. **Question of the Week**: [A thought-provoking question for their business]\n\nWhat are you working on right now? Hit reply and let us know!\n\nBest,\n[Your Name]`
      }
    }
  };

  const HOOK_LIBRARY = {
    mistake: 'The #1 mistake most [Audience] make when trying to [Goal]...',
    curiosity: 'Nobody is talking about this simple shortcut for [Topic]...',
    'stop-doing': 'Stop doing [Common Habit] if you actually want [Result]...',
    'quick-fix': 'Here is exactly how I fix [Specific Problem] in under 60 seconds...',
    tools: '3 free tools every [Audience] needs to start using today...'
  };

  const activeBrandSelect = document.getElementById('activeBrandSelect');
  if (!activeBrandSelect) return;

  const states = Object.fromEntries(Object.keys(CONFIG).map(channel => [channel, {
    record: null,
    records: []
  }]));
  let loadSequence = 0;

  function brandLabel(brandId) {
    return BRAND_LABELS[brandId] || brandId || 'selected brand';
  }

  function setMessage(element, message, isError = false) {
    if (!element) return;
    element.textContent = message;
    element.classList.toggle('error', isError);
  }

  function statusClass(status) {
    return String(status || 'Draft').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  }

  function normalize(value) {
    return typeof value === 'string' ? value.toLowerCase().replace(/[^a-z0-9]+/g, '') : '';
  }

  function matchesChannel(record, channel) {
    const values = [record.channel, record.contentType, record.format].map(normalize);
    if (channel === 'reels') return values.some(value => value.includes('reel'));
    return values.some(value => value === channel || value.includes(channel));
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, {cache: 'no-store', ...options});
    let payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {};
    }
    if (!response.ok) throw new Error(payload.error || 'Could not save or load this content record.');
    return payload;
  }

  async function postAction(record, action, fields = {}) {
    const payload = await requestJson(`/api/content/${encodeURIComponent(record.id)}/actions`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action, ...fields})
    });
    return payload.record;
  }

  function formatLabel(format) {
    const labels = {
      'blog-article': 'Blog article',
      'reel-script': 'Reel script / caption',
      'email-draft': 'Email draft',
      'linkedin-article': 'LinkedIn article'
    };
    return labels[format] || format || 'Content draft';
  }

  function recordPayload(channel, brandId, values) {
    const config = CONFIG[channel];
    const existing = states[channel].record;
    return {
      brandId,
      title: values.title,
      contentType: existing?.contentType || config.contentType,
      channel: existing?.channel || config.channel,
      format: existing?.format || config.format,
      body: values.body,
      brief: values.brief,
      sourceUrl: existing?.sourceUrl || '',
      sourceModule: existing?.sourceModule || 'channel-editor',
      sourceId: existing?.sourceId || '',
      targetDate: values.targetDate || null
    };
  }

  function valuesFor(form) {
    const values = {
      title: form.elements.title.value.trim(),
      brief: form.elements.brief.value,
      body: form.elements.body.value,
      targetDate: form.elements.targetDate.value || null
    };
    if (!values.title || !values.body.trim()) {
      throw new Error('Add a title and content before saving or submitting.');
    }
    return values;
  }

  function currentBrandId() {
    return activeBrandSelect.value;
  }

  function renderStatus(record) {
    const badge = document.createElement('span');
    badge.className = `st ${record.status === 'Draft' ? 'draft' : ''} status-${statusClass(record.status)}`;
    const dot = document.createElement('span');
    dot.className = 'dot';
    const label = document.createElement('span');
    label.className = 'status-label';
    label.textContent = record.status;
    badge.append(dot, label);
    return badge;
  }

  function actionButton(label, callback, primary = false) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `act${primary ? ' primary' : ''}`;
    button.textContent = label;
    button.addEventListener('click', callback);
    return button;
  }

  function populateEditor(channel, record) {
    const config = CONFIG[channel];
    const state = states[channel];
    const form = document.getElementById(config.formId);
    if (!form) return;
    state.record = record;
    form.elements.title.value = record.title || '';
    form.elements.brief.value = record.brief || '';
    form.elements.body.value = record.body || '';
    form.elements.targetDate.value = record.targetDate || '';
    const cancel = form.querySelector(`[data-channel-cancel="${channel}"]`);
    if (cancel) cancel.hidden = false;
    const save = form.querySelector('button[type="submit"]');
    if (save) save.textContent = record.status === 'Draft' ? 'Update draft' : 'Save changes';
    const submit = form.querySelector(`[data-channel-submit-review="${channel}"]`);
    if (submit) {
      submit.textContent = record.status === 'Changes Requested' ? 'Submit again' : 'Submit for review';
      submit.disabled = !['Draft', 'Changes Requested'].includes(record.status);
      submit.title = submit.disabled ? 'This record is already under review or has completed review. Use Approvals for its next status.' : '';
    }
    const warnings = {
      Draft: 'Saving this Draft keeps it in Draft.',
      'Needs Review': 'Saving edits to a Needs Review record marks it Changes Requested; submit again after editing.',
      'Changes Requested': 'Saving edits to a Changes Requested record keeps it Changes Requested until you submit again.',
      Approved: 'Saving edits to an Approved record marks it Changes Requested; it will need review again.'
    };
    const warning = warnings[record.status] || `This record is ${record.status}; use Approvals for its next workflow action.`;
    setMessage(document.getElementById(config.statusId), `${warning} · ${brandLabel(record.brandId)}.`);
    form.elements.title.focus();
  }

  function resetEditor(channel, message = 'Ready for a new draft.') {
    const config = CONFIG[channel];
    const state = states[channel];
    const form = document.getElementById(config.formId);
    if (!form) return;
    state.record = null;
    form.reset();
    const cancel = form.querySelector(`[data-channel-cancel="${channel}"]`);
    if (cancel) cancel.hidden = true;
    const save = form.querySelector('button[type="submit"]');
    if (save) save.textContent = 'Save as draft';
    const submit = form.querySelector(`[data-channel-submit-review="${channel}"]`);
    if (submit) {
      submit.textContent = 'Submit for review';
      submit.disabled = false;
      submit.title = '';
    }
    setMessage(document.getElementById(config.statusId), message);
  }

  function buildHandoff(record, channel) {
    const config = CONFIG[channel];
    return [
      `# ${config.handoffTitle}`,
      `Brand: ${brandLabel(record.brandId)}`,
      `Channel: ${config.label}`,
      `Status: ${record.status}`,
      `Planning target date: ${record.targetDate || 'Not set'}`,
      '',
      `## ${config.titleLabel}`,
      record.title,
      '',
      `## ${config.briefLabel}`,
      record.brief || '(Not provided)',
      '',
      `## ${config.bodyLabel}`,
      record.body,
      '',
      '---',
      'Manual handoff only. This local export did not send, schedule, or publish content.'
    ].join('\n');
  }

  function safeFilePart(value) {
    return String(value || '')
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 72) || 'untitled';
  }

  function downloadHandoff(record, channel) {
    if (!record || record.status !== 'Approved') return;
    const content = buildHandoff(record, channel);
    const blobUrl = URL.createObjectURL(new Blob([content], {type: 'text/markdown;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = `${record.brandId}-${channel}-${safeFilePart(record.title)}-handoff.md`;
    link.hidden = true;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    setMessage(document.getElementById(CONFIG[channel].statusId), 'Downloaded a local handoff. No content was sent, scheduled, or published.');
  }

  function renderRecord(channel, record) {
    const config = CONFIG[channel];
    const article = document.createElement('article');
    article.className = 'channel-record-card';
    const head = document.createElement('div');
    head.className = 'channel-record-head';
    const title = document.createElement('h3');
    title.textContent = record.title;
    head.append(title, renderStatus(record));

    const meta = document.createElement('div');
    meta.className = 'channel-record-meta';
    meta.textContent = `${formatLabel(record.format)} · ${record.targetDate ? `Target ${record.targetDate}` : 'No target date'}`;
    article.append(head, meta);

    if (record.brief) {
      const brief = document.createElement('div');
      brief.className = 'channel-record-brief';
      brief.textContent = `${config.briefLabel}: ${record.brief}`;
      article.append(brief);
    }

    const details = document.createElement('details');
    details.className = 'channel-record-brief';
    const summary = document.createElement('summary');
    summary.textContent = `View ${config.bodyLabel.toLowerCase()}`;
    const body = document.createElement('div');
    body.className = 'channel-record-body';
    body.textContent = record.body;
    details.append(summary, body);
    article.append(details);

    const actions = document.createElement('div');
    actions.className = 'channel-record-actions';
    if (['Draft', 'Needs Review', 'Changes Requested', 'Approved'].includes(record.status)) {
      actions.append(actionButton('Edit', () => populateEditor(channel, record)));
    }
    if (record.status === 'Draft') {
      actions.append(actionButton('Submit for review', () => {
        populateEditor(channel, record);
        submitRecordForReview(channel, record);
      }, true));
    } else if (record.status === 'Changes Requested') {
      actions.append(actionButton('Submit again', () => {
        populateEditor(channel, record);
        submitRecordForReview(channel, record);
      }, true));
    } else if (record.status === 'Approved') {
      actions.append(actionButton('Download handoff', () => downloadHandoff(record, channel), true));
    }
    if (actions.childElementCount) article.append(actions);
    return article;
  }

  function renderChannelRecords(channel, records, brandId) {
    const config = CONFIG[channel];
    const state = states[channel];
    const list = document.getElementById(config.listId);
    const brandLabels = document.querySelectorAll(`[data-channel-brand-label="${channel}"]`);
    brandLabels.forEach(element => { element.textContent = brandLabel(brandId); });
    if (!list) return;

    const filtered = records.filter(record => record.brandId === brandId && matchesChannel(record, channel));
    state.records = filtered;
    if (state.record && state.record.brandId !== brandId) resetEditor(channel, `Switched to ${brandLabel(brandId)}. Start a new draft for this brand.`);
    if (state.record) {
      const latest = filtered.find(record => record.id === state.record.id);
      if (latest) state.record = latest;
    }
    list.replaceChildren();
    if (!filtered.length) {
      const empty = document.createElement('div');
      empty.className = 'record-empty';
      empty.textContent = `No saved ${config.label} records for ${brandLabel(brandId)}. Save a draft to start.`;
      list.append(empty);
      return;
    }
    filtered.forEach(record => list.append(renderRecord(channel, record)));
  }

  async function refresh(message = '') {
    const brandId = currentBrandId();
    const sequence = ++loadSequence;
    Object.keys(CONFIG).forEach(channel => {
      const config = CONFIG[channel];
      const labels = document.querySelectorAll(`[data-channel-brand-label="${channel}"]`);
      labels.forEach(element => { element.textContent = brandLabel(brandId); });
      setMessage(document.getElementById(config.statusId), `Loading ${config.label} records for ${brandLabel(brandId)}…`);
    });
    try {
      const payload = await requestJson(`/api/content?brand=${encodeURIComponent(brandId)}`);
      if (sequence !== loadSequence || brandId !== currentBrandId()) return;
      const records = (payload.records || []).filter(record => record.brandId === brandId);
      Object.keys(CONFIG).forEach(channel => renderChannelRecords(channel, records, brandId));
      Object.keys(CONFIG).forEach(channel => {
        const config = CONFIG[channel];
        const count = states[channel].records.length;
        setMessage(document.getElementById(config.statusId), message || `${count} saved ${config.label} record${count === 1 ? '' : 's'} for ${brandLabel(brandId)}.`);
      });
    } catch (error) {
      if (sequence !== loadSequence) return;
      Object.keys(CONFIG).forEach(channel => {
        renderChannelRecords(channel, [], brandId);
        setMessage(document.getElementById(CONFIG[channel].statusId), error.message || 'Could not load shared content records.', true);
      });
    }
  }

  function formButtons(channel, disabled) {
    const form = document.getElementById(CONFIG[channel].formId);
    form?.querySelectorAll('button').forEach(button => { button.disabled = disabled; });
  }

  async function syncViews(message) {
    if (window.ContentHub?.refresh) await window.ContentHub.refresh(message);
    await refresh(message);
  }

  async function saveDraft(channel) {
    const config = CONFIG[channel];
    const state = states[channel];
    const form = document.getElementById(config.formId);
    if (!form.reportValidity()) return;
    let values;
    try {
      values = valuesFor(form);
    } catch (error) {
      setMessage(document.getElementById(config.statusId), error.message, true);
      return;
    }
    const brandId = currentBrandId();
    const payload = recordPayload(channel, brandId, values);
    formButtons(channel, true);
    setMessage(document.getElementById(config.statusId), 'Saving to local shared records…');
    try {
      let record;
      if (state.record) {
        const action = state.record.status === 'Draft' ? 'save_draft' : 'edit';
        record = await postAction(state.record, action, {
          ...values,
          ...(action === 'edit' ? {reviewNote: state.record.reviewNote || ''} : {})
        });
      } else {
        const result = await requestJson('/api/content/drafts', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        record = result.record;
      }
      state.record = record;
      const cancel = form.querySelector(`[data-channel-cancel="${channel}"]`);
      if (cancel) cancel.hidden = false;
      const save = form.querySelector('button[type="submit"]');
      if (save) save.textContent = record.status === 'Draft' ? 'Update draft' : 'Save changes';
      const submit = form.querySelector(`[data-channel-submit-review="${channel}"]`);
      if (submit) {
        submit.disabled = !['Draft', 'Changes Requested'].includes(record.status);
        submit.textContent = record.status === 'Changes Requested' ? 'Submit again' : 'Submit for review';
      }
      await syncViews(`${record.status} saved for ${brandLabel(brandId)}. Nothing was published or scheduled.`);
    } catch (error) {
      setMessage(document.getElementById(config.statusId), error.message || 'Could not save this record.', true);
    } finally {
      formButtons(channel, false);
    }
  }

  async function submitRecordForReview(channel, record = states[channel].record) {
    const config = CONFIG[channel];
    const state = states[channel];
    const form = document.getElementById(config.formId);
    if (!form.reportValidity()) return;
    let values;
    try {
      values = valuesFor(form);
    } catch (error) {
      setMessage(document.getElementById(config.statusId), error.message, true);
      return;
    }
    const brandId = currentBrandId();
    const payload = recordPayload(channel, brandId, values);
    formButtons(channel, true);
    setMessage(document.getElementById(config.statusId), 'Submitting to the local review queue…');
    try {
      let updated;
      const target = record || state.record;
      if (!target) {
        const result = await requestJson('/api/content', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        updated = result.record;
      } else if (target.status === 'Draft') {
        const saved = await postAction(target, 'save_draft', values);
        updated = await postAction(saved, 'submit_for_review');
      } else if (target.status === 'Changes Requested') {
        const edited = await postAction(target, 'edit', {
          ...values,
          reviewNote: target.reviewNote || ''
        });
        updated = await postAction(edited, 'resubmit');
      } else {
        throw new Error('This record is already under review or has completed review. Use Approvals for its next status.');
      }
      state.record = updated;
      const cancel = form.querySelector(`[data-channel-cancel="${channel}"]`);
      if (cancel) cancel.hidden = false;
      const save = form.querySelector('button[type="submit"]');
      if (save) save.textContent = 'Save changes';
      const submit = form.querySelector(`[data-channel-submit-review="${channel}"]`);
      if (submit) {
        submit.disabled = true;
        submit.textContent = 'In review';
      }
      await syncViews(`Submitted to Approvals for ${brandLabel(brandId)}. Approval does not schedule or publish.`);
    } catch (error) {
      setMessage(document.getElementById(config.statusId), error.message || 'Could not submit this record for review.', true);
    } finally {
      formButtons(channel, false);
      const submit = form.querySelector(`[data-channel-submit-review="${channel}"]`);
      if (submit && state.record) {
        submit.disabled = !['Draft', 'Changes Requested'].includes(state.record.status);
        if (!submit.disabled) submit.textContent = state.record.status === 'Changes Requested' ? 'Submit again' : 'Submit for review';
      }
    }
  }

  function applyTemplate(channel) {
    const config = CONFIG[channel];
    const select = document.getElementById(`${channel}StarterTemplate`);
    if (!select || !select.value) {
      setMessage(document.getElementById(config.statusId), 'Please select a blueprint or framework first.', true);
      return;
    }
    const template = TEMPLATES[channel]?.[select.value];
    if (!template) return;
    const form = document.getElementById(config.formId);
    if (!form) return;
    if (form.elements.body.value.trim() && !window.confirm('Replace current editor text with this blueprint?')) {
      return;
    }
    form.elements.title.value = template.title || '';
    form.elements.brief.value = template.brief || '';
    form.elements.body.value = template.body || '';
    setMessage(document.getElementById(config.statusId), `Loaded "${select.options[select.selectedIndex].text}" template.`);
    form.elements.body.focus();
  }

  function applyHook(channel) {
    const config = CONFIG[channel];
    const select = document.getElementById(`${channel}HookLibrary`);
    if (!select || !select.value) {
      setMessage(document.getElementById(config.statusId), 'Please select a hook from the library first.', true);
      return;
    }
    const hookText = HOOK_LIBRARY[select.value];
    if (!hookText) return;
    const form = document.getElementById(config.formId);
    if (!form) return;
    const brief = form.elements.brief;
    const current = brief.value.trim();
    brief.value = current ? `${current}\n\n[Hook]: ${hookText}` : `[Hook]: ${hookText}`;
    setMessage(document.getElementById(config.statusId), `Inserted hook into brief.`);
    brief.focus();
  }

  Object.keys(CONFIG).forEach(channel => {
    const config = CONFIG[channel];
    const form = document.getElementById(config.formId);
    if (!form) return;
    form.addEventListener('submit', event => {
      event.preventDefault();
      saveDraft(channel);
    });
    form.querySelector(`[data-channel-submit-review="${channel}"]`)?.addEventListener('click', () => submitRecordForReview(channel));
    form.querySelector(`[data-channel-cancel="${channel}"]`)?.addEventListener('click', () => resetEditor(channel));
    document.querySelector(`[data-channel-apply-template="${channel}"]`)?.addEventListener('click', () => applyTemplate(channel));
    document.querySelector(`[data-channel-apply-hook="${channel}"]`)?.addEventListener('click', () => applyHook(channel));
  });

  activeBrandSelect.addEventListener('change', () => refresh());
  window.ChannelEditors = {refresh};
})();
