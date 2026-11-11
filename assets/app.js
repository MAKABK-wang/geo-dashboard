/* ==========================================================================
   GEO 可视化仪表盘 · 交互脚本
   - 全站全文检索（标题 / 正文 / FAQ / AI 原回答）
   - 主题切换、移动端目录、FAQ 筛选与复制
   - 无第三方依赖，所有内容在首屏 HTML 中，禁用 JS 也可阅读
   ========================================================================== */
(function () {
  'use strict';

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function squash(text) {
    return String(text || '').replace(/\s+/g, ' ').trim();
  }

  function escapeHTML(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function highlight(text, terms) {
    var lower = text.toLowerCase();
    var ranges = [];
    terms.forEach(function (term) {
      var pos = 0;
      while ((pos = lower.indexOf(term, pos)) !== -1) {
        ranges.push([pos, pos + term.length]);
        pos += term.length;
      }
    });
    if (!ranges.length) return escapeHTML(text);
    ranges.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [];
    ranges.forEach(function (range) {
      var last = merged[merged.length - 1];
      if (last && range[0] <= last[1]) {
        last[1] = Math.max(last[1], range[1]);
      } else {
        merged.push(range.slice());
      }
    });
    var out = '';
    var cursor = 0;
    merged.forEach(function (range) {
      out += escapeHTML(text.slice(cursor, range[0]));
      out += '<mark>' + escapeHTML(text.slice(range[0], range[1])) + '</mark>';
      cursor = range[1];
    });
    return out + escapeHTML(text.slice(cursor));
  }

  /* --------------------------------------------------------------- theme */
  var themeToggle = $('#themeToggle');
  var root = document.documentElement;

  function setTheme(theme, persist) {
    root.setAttribute('data-theme', theme);
    root.style.colorScheme = theme;
    if (themeToggle) {
      themeToggle.setAttribute('aria-label', theme === 'dark' ? '切换到浅色主题' : '切换到深色主题');
    }
    if (persist) {
      try { localStorage.setItem('geo-theme', theme); } catch (e) {}
    }
  }

  if (themeToggle) {
    setTheme(root.getAttribute('data-theme') === 'light' ? 'light' : 'dark', false);
    themeToggle.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      setTheme(next, true);
    });
  }

  /* ---------------------------------------------------------- mobile nav */
  var navToggle = $('#navToggle');
  var mobileNav = $('#mobileNav');

  function closeMobileNav() {
    if (!mobileNav || mobileNav.hidden) return;
    mobileNav.hidden = true;
    if (navToggle) navToggle.setAttribute('aria-expanded', 'false');
  }

  if (navToggle && mobileNav) {
    navToggle.addEventListener('click', function () {
      var willOpen = mobileNav.hidden;
      mobileNav.hidden = !willOpen;
      navToggle.setAttribute('aria-expanded', String(willOpen));
    });
    mobileNav.addEventListener('click', function (event) {
      if (event.target.closest('a')) closeMobileNav();
    });
    window.addEventListener('resize', function () {
      if (window.innerWidth > 1120) closeMobileNav();
    });
  }

  /* ------------------------------------------------------------- to top */
  var toTop = $('#toTop');
  if (toTop) {
    toTop.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' });
    });
    var toggleTop = function () {
      if (window.scrollY > 700) {
        toTop.hidden = false;
      } else {
        toTop.hidden = true;
      }
    };
    window.addEventListener('scroll', toggleTop, { passive: true });
    toggleTop();
  }

  /* ----------------------------------------------------------- scrollspy */
  var navLinks = $$('.site-nav a[data-nav]');
  var spySections = navLinks.map(function (link) {
    var id = link.getAttribute('href');
    return { link: link, section: id && id.length > 1 ? document.getElementById(id.slice(1)) : null };
  }).filter(function (entry) { return entry.section; });

  function updateSpy() {
    if (!spySections.length) return;
    var marker = window.scrollY + 130;
    var current = null;
    spySections.forEach(function (entry) {
      if (entry.section.offsetTop <= marker) current = entry;
    });
    if (window.innerHeight + window.scrollY >= document.body.scrollHeight - 4) {
      current = spySections[spySections.length - 1];
    }
    spySections.forEach(function (entry) {
      if (entry === current) {
        entry.link.setAttribute('aria-current', 'true');
      } else {
        entry.link.removeAttribute('aria-current');
      }
    });
  }

  if (spySections.length) {
    var spyTick = false;
    window.addEventListener('scroll', function () {
      if (spyTick) return;
      spyTick = true;
      window.requestAnimationFrame(function () {
        updateSpy();
        spyTick = false;
      });
    }, { passive: true });
    updateSpy();
  }

  /* --------------------------------------------------------------- FAQ */
  var faqChips = $$('.chip[data-filter]');
  var faqGroups = $$('.faq-group');
  var faqStatus = $('#faqFilterStatus');
  var faqToggleAll = $('#faqToggleAll');
  var faqExpanded = false;

  function setFaqFilter(category) {
    if (!faqChips.length) return;
    var activeChip = null;
    var visible = 0;
    faqChips.forEach(function (chip) {
      var pressed = chip.dataset.filter === category;
      chip.setAttribute('aria-pressed', String(pressed));
      if (pressed) activeChip = chip;
    });
    faqGroups.forEach(function (group) {
      var show = category === 'all' || group.dataset.faqGroup === category;
      group.hidden = !show;
      if (show) visible += $$('.faq-item', group).length;
    });
    if (faqStatus) {
      faqStatus.textContent = '已显示 ' + visible + ' 条 FAQ' +
        (category === 'all' ? '' : ' · 分类：' + (activeChip ? activeChip.dataset.label || activeChip.textContent.trim() : category));
    }
    if (faqToggleAll) {
      faqExpanded = false;
      faqToggleAll.setAttribute('aria-expanded', 'false');
      var label = faqToggleAll.querySelector('span');
      if (label) label.textContent = '展开全部';
    }
  }

  faqChips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      setFaqFilter(chip.dataset.filter || 'all');
    });
  });

  if (faqToggleAll) {
    faqToggleAll.addEventListener('click', function () {
      faqExpanded = !faqExpanded;
      faqGroups.forEach(function (group) {
        if (group.hidden) return;
        $$('.faq-item', group).forEach(function (item) { item.open = faqExpanded; });
      });
      faqToggleAll.setAttribute('aria-expanded', String(faqExpanded));
      var label = faqToggleAll.querySelector('span');
      if (label) label.textContent = faqExpanded ? '收起全部' : '展开全部';
    });
  }

  /* ------------------------------------------------------------ reveal */
  function openAncestors(element) {
    var node = element.parentElement;
    while (node) {
      if (node.tagName === 'DETAILS') node.open = true;
      node = node.parentElement;
    }
    if (element.tagName === 'DETAILS') element.open = true;
  }

  function flash(element) {
    element.classList.remove('is-flash');
    void element.offsetWidth;
    element.classList.add('is-flash');
    window.setTimeout(function () { element.classList.remove('is-flash'); }, 2100);
  }

  function reveal(element, options) {
    if (!element) return;
    var group = element.closest('.faq-group');
    if (group && group.hidden) setFaqFilter('all');
    openAncestors(element);
    var behavior = reducedMotion ? 'auto' : 'smooth';
    element.scrollIntoView({ behavior: behavior, block: options && options.block ? options.block : 'center' });
    flash(element);
    if (!element.hasAttribute('tabindex') && element.tagName !== 'A' && element.tagName !== 'BUTTON') {
      element.setAttribute('tabindex', '-1');
    }
    try { element.focus({ preventScroll: true }); } catch (e) {}
  }

  function revealHash() {
    var hash = window.location.hash;
    if (!hash || hash.length < 2) return;
    var target = document.getElementById(decodeURIComponent(hash.slice(1)));
    if (!target) return;
    window.setTimeout(function () { reveal(target, { block: 'center' }); }, 80);
  }

  window.addEventListener('hashchange', revealHash);

  /* ------------------------------------------------------------- search */
  var searchRoot = $('#search');
  var searchInput = $('#searchInput');
  var searchPanel = $('#searchPanel');
  var searchList = $('#searchResults');
  var searchMeta = $('#searchMeta');
  var searchClear = $('#searchClear');
  var searchIndex = [];
  var activeResult = -1;

  function itemText(element) {
    if (element.classList.contains('answer-item')) {
      var body = $('.answer-body', element);
      if (body) return squash(body.textContent);
    }
    if (element.classList.contains('faq-item')) {
      var question = $('.faq-question', element);
      var answer = $('.faq-answer', element);
      return squash((question ? question.textContent : '') + ' ' + (answer ? answer.textContent : ''));
    }
    if (element.classList.contains('gap-row')) {
      var qtext = $('.gap-qtext', element);
      if (qtext) return squash(qtext.textContent);
    }
    var clone = element.cloneNode(true);
    $$('.faq-actions, .sr-only, [hidden], .row-idx, .answer-badge, .answer-index, .answer-summary', clone)
      .forEach(function (node) { node.remove(); });
    return squash(clone.textContent);
  }

  function buildIndex() {
    searchIndex = $$('[data-search-item]').map(function (element, index) {
      if (!element.id) element.id = 'search-target-' + index;
      var title = squash(element.dataset.searchTitle || element.getAttribute('aria-label') || element.id);
      var display = itemText(element);
      return {
        element: element,
        id: element.id,
        title: title,
        titleLower: title.toLowerCase(),
        type: element.dataset.searchType || '内容',
        section: element.dataset.searchSection || '',
        display: display,
        text: display.toLowerCase(),
        order: index
      };
    });
  }

  function snippetFor(item, terms) {
    var text = item.text;
    var best = -1;
    terms.forEach(function (term) {
      var pos = text.indexOf(term);
      if (pos !== -1 && (best === -1 || pos < best)) best = pos;
    });
    if (best === -1) best = 0;
    var start = Math.max(0, best - 26);
    var end = Math.min(text.length, start + 110);
    var fragment = item.display.slice(start, end);
    if (start > 0) fragment = '…' + fragment;
    if (end < text.length) fragment += '…';
    return fragment;
  }

  function search(query) {
    var terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) return [];
    var results = [];
    searchIndex.forEach(function (item) {
      var score = 0;
      var matchedAll = true;
      terms.forEach(function (term) {
        var inTitle = item.titleLower.indexOf(term);
        var inText = item.text.indexOf(term);
        if (inTitle === -1 && inText === -1) {
          matchedAll = false;
          return;
        }
        if (inTitle !== -1) score += 60 + Math.max(0, 24 - inTitle);
        var occurrences = 0;
        var pos = 0;
        while ((pos = item.text.indexOf(term, pos)) !== -1 && occurrences < 12) {
          occurrences += 1;
          pos += term.length;
        }
        score += occurrences * 3;
        if (inText !== -1) score += 8;
        if (item.titleLower === term) score += 80;
      });
      if (matchedAll) results.push({ item: item, score: score });
    });
    results.sort(function (a, b) {
      return b.score - a.score || a.item.order - b.item.order;
    });
    return results.slice(0, 20).map(function (entry) { return entry.item; });
  }

  function setActive(index) {
    var items = $$('.search-item', searchList);
    if (!items.length) {
      activeResult = -1;
      searchInput.removeAttribute('aria-activedescendant');
      return;
    }
    activeResult = Math.max(0, Math.min(index, items.length - 1));
    items.forEach(function (node, i) {
      var active = i === activeResult;
      node.classList.toggle('active', active);
      node.setAttribute('aria-selected', String(active));
    });
    var activeNode = items[activeResult];
    searchInput.setAttribute('aria-activedescendant', activeNode.id);
    activeNode.scrollIntoView({ block: 'nearest' });
  }

  function renderResults(results, terms, query) {
    searchList.innerHTML = '';
    if (!results.length) {
      var empty = document.createElement('li');
      empty.className = 'search-empty';
      empty.setAttribute('role', 'presentation');
      empty.innerHTML = '没有找到与 <b>' + escapeHTML(query) + '</b> 相关的内容，试试「读码器」「锂电」「FAQ」。';
      searchList.appendChild(empty);
      searchMeta.textContent = '0 条结果';
      searchInput.removeAttribute('aria-activedescendant');
      activeResult = -1;
      return;
    }

    results.forEach(function (item, index) {
      var li = document.createElement('li');
      li.className = 'search-item';
      li.id = 'search-opt-' + index;
      li.setAttribute('role', 'option');
      li.setAttribute('aria-selected', 'false');
      li.dataset.target = item.id;
      li.innerHTML =
        '<div class="search-item-top">' +
          '<span class="search-type">' + escapeHTML(item.type) + '</span>' +
          '<span class="search-path">' + escapeHTML(item.section) + '</span>' +
        '</div>' +
        '<p class="search-title">' + highlight(item.title, terms) + '</p>' +
        '<p class="search-snippet">' + highlight(snippetFor(item, terms), terms) + '</p>';
      searchList.appendChild(li);
    });

    searchMeta.textContent = '找到 ' + results.length + ' 条结果 · 关键词「' + query + '」';
    setActive(0);
  }

  function openPanel() {
    if (!searchPanel) return;
    searchPanel.hidden = false;
    searchInput.setAttribute('aria-expanded', 'true');
  }

  function closePanel() {
    if (!searchPanel) return;
    searchPanel.hidden = true;
    searchInput.setAttribute('aria-expanded', 'false');
    searchInput.removeAttribute('aria-activedescendant');
    activeResult = -1;
  }

  function performSearch(raw) {
    var query = raw.trim();
    if (!query) {
      closePanel();
      if (searchMeta) searchMeta.textContent = '输入关键词开始检索';
      if (searchClear) searchClear.hidden = true;
      searchRoot.classList.remove('has-value');
      return;
    }
    if (searchClear) searchClear.hidden = false;
    searchRoot.classList.add('has-value');
    var terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    var results = search(query);
    renderResults(results, terms, query);
    openPanel();
  }

  function selectResult(id) {
    var item = searchIndex.filter(function (entry) { return entry.id === id; })[0];
    var element = item ? item.element : document.getElementById(id);
    if (!element) return;
    closePanel();
    var params = new URLSearchParams(window.location.search);
    if (searchInput.value.trim()) {
      params.set('q', searchInput.value.trim());
    } else {
      params.delete('q');
    }
    var search = params.toString();
    try {
      window.history.replaceState(null, '', window.location.pathname + (search ? '?' + search : '') + '#' + id);
    } catch (e) {}
    reveal(element, { block: 'center' });
    if (searchInput) searchInput.blur();
  }

  if (searchInput && searchPanel && searchList) {
    buildIndex();

    searchInput.addEventListener('input', function () {
      performSearch(searchInput.value);
    });

    searchInput.addEventListener('focus', function () {
      if (searchInput.value.trim()) performSearch(searchInput.value);
    });

    searchInput.addEventListener('keydown', function (event) {
      var items = $$('.search-item', searchList);
      if (event.key === 'ArrowDown') {
        if (searchPanel.hidden) {
          if (searchInput.value.trim()) performSearch(searchInput.value);
        } else {
          event.preventDefault();
          setActive(activeResult + 1);
        }
      } else if (event.key === 'ArrowUp') {
        if (!searchPanel.hidden) {
          event.preventDefault();
          setActive(activeResult - 1);
        }
      } else if (event.key === 'Enter') {
        if (!searchPanel.hidden && items.length) {
          event.preventDefault();
          var target = items[Math.max(0, activeResult)];
          if (target) selectResult(target.dataset.target);
        }
      } else if (event.key === 'Escape') {
        if (!searchPanel.hidden) {
          event.preventDefault();
          closePanel();
        }
      } else if (event.key === 'Tab') {
        closePanel();
      }
    });

    searchList.addEventListener('click', function (event) {
      var item = event.target.closest('.search-item');
      if (item && item.dataset.target) selectResult(item.dataset.target);
    });

    searchList.addEventListener('mousemove', function (event) {
      var item = event.target.closest('.search-item');
      if (!item) return;
      var items = $$('.search-item', searchList);
      var index = items.indexOf(item);
      if (index !== -1 && index !== activeResult) setActive(index);
    });

    if (searchClear) {
      searchClear.addEventListener('click', function () {
        searchInput.value = '';
        performSearch('');
        var params = new URLSearchParams(window.location.search);
        params.delete('q');
        var search = params.toString();
        try {
          window.history.replaceState(null, '', window.location.pathname + (search ? '?' + search : '') + window.location.hash);
        } catch (e) {}
        searchInput.focus();
      });
    }

    document.addEventListener('click', function (event) {
      if (searchRoot && !searchRoot.contains(event.target)) closePanel();
    });

    document.addEventListener('keydown', function (event) {
      var active = document.activeElement;
      var typing = active && (/^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName) || active.isContentEditable);
      var isShortcut = (event.key === '/' && !typing) ||
        ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k');
      if (isShortcut) {
        event.preventDefault();
        searchInput.focus();
        searchInput.select();
        if (searchInput.value.trim()) performSearch(searchInput.value);
        openPanel();
      }
      if (event.key === 'Escape') {
        closeMobileNav();
      }
    });

    var initialQuery = new URLSearchParams(window.location.search).get('q');
    if (initialQuery) {
      searchInput.value = initialQuery;
      performSearch(initialQuery);
    }
  }

  /* -------------------------------------------------------------- copy */
  function fallbackCopy(text) {
    var area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.top = '-1000px';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(area);
    return ok;
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(function () { return true; }).catch(function () {
        return fallbackCopy(text);
      });
    }
    return Promise.resolve(fallbackCopy(text));
  }

  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-copy-selector], [data-copy-link]');
    if (!button) return;
    var text = '';
    if (button.dataset.copySelector) {
      var target = $(button.dataset.copySelector);
      if (target) text = target.textContent || '';
    } else if (button.dataset.copyLink) {
      text = window.location.origin + window.location.pathname + '#' + button.dataset.copyLink;
    }
    if (!text.trim()) return;
    var original = button.textContent;
    copyText(text.trim()).then(function (ok) {
      button.textContent = ok ? '已复制' : '复制失败';
      button.classList.toggle('is-copied', ok);
      window.setTimeout(function () {
        button.textContent = original;
        button.classList.remove('is-copied');
      }, 1600);
    });
  });

  /* --------------------------------------------------------- suggestions */
  var suggestDialog = $('#suggestDialog');
  var suggestForm = $('#suggestForm');
  var suggestStatus = $('#suggestStatus');
  var suggestSubmit = $('#suggestSubmit');
  var suggestCounter = $('#suggestCounter');
  var suggestSuccess = $('#suggestSuccess');
  var suggestReceipt = $('#suggestReceipt');
  var suggestFallback = $('#suggestFallback');
  var suggestFallbackText = $('#suggestFallbackText');
  var suggestGithub = $('#suggestGithub');
  var suggestCopy = $('#suggestCopy');
  var suggestOpeners = $$('[data-open-suggest]');
  var lastSuggestion = null;
  var suggestOpener = null;

  function currentSectionLabel() {
    var marker = 170;
    var current = '';
    $$('[data-section-label]').forEach(function (section) {
      if (section.getBoundingClientRect().top <= marker) {
        current = section.dataset.sectionLabel;
      }
    });
    return current;
  }

  function resetSuggestDialog() {
    if (!suggestForm || !suggestDialog) return;
    suggestDialog.classList.remove('is-success');
    suggestForm.hidden = false;
    suggestForm.reset();
    if (suggestSuccess) suggestSuccess.hidden = true;
    if (suggestFallback) suggestFallback.hidden = true;
    if (suggestStatus) {
      suggestStatus.textContent = '';
      suggestStatus.className = 'form-status';
    }
    if (suggestSubmit) {
      suggestSubmit.disabled = false;
      suggestSubmit.textContent = '提交建议';
    }
    if (suggestCounter) suggestCounter.textContent = '0 / 1000';
  }

  function openSuggestDialog(opener) {
    if (!suggestDialog) return;
    suggestOpener = opener || document.activeElement;
    if (suggestSuccess && !suggestSuccess.hidden) resetSuggestDialog();
    var locationField = suggestForm ? suggestForm.elements.location : null;
    if (locationField && !locationField.value) {
      locationField.value = currentSectionLabel();
    }
    document.body.classList.add('dialog-open');
    if (typeof suggestDialog.showModal === 'function') {
      suggestDialog.showModal();
    } else {
      suggestDialog.setAttribute('open', '');
    }
    var firstField = suggestForm ? suggestForm.querySelector('select, textarea, input') : null;
    if (firstField) window.setTimeout(function () { firstField.focus(); }, 40);
  }

  function closeSuggestDialog() {
    if (!suggestDialog) return;
    if (suggestDialog.open && typeof suggestDialog.close === 'function') {
      suggestDialog.close();
    } else {
      suggestDialog.removeAttribute('open');
      document.body.classList.remove('dialog-open');
    }
    if (suggestOpener && typeof suggestOpener.focus === 'function') {
      try { suggestOpener.focus(); } catch (e) {}
    }
  }

  suggestOpeners.forEach(function (button) {
    button.addEventListener('click', function () { openSuggestDialog(button); });
  });

  $$('[data-close-dialog]', suggestDialog || document).forEach(function (button) {
    button.addEventListener('click', closeSuggestDialog);
  });

  if (suggestDialog) {
    suggestDialog.addEventListener('close', function () {
      document.body.classList.remove('dialog-open');
    });
    suggestDialog.addEventListener('cancel', function () {
      document.body.classList.remove('dialog-open');
    });
    suggestDialog.addEventListener('click', function (event) {
      if (event.target === suggestDialog) closeSuggestDialog();
    });
  }

  if (suggestDialog && suggestForm) {
    var messageField = suggestForm.elements.message;
    if (messageField && suggestCounter) {
      messageField.addEventListener('input', function () {
        suggestCounter.textContent = messageField.value.length + ' / 1000';
      });
    }

    function suggestionText() {
      var data = new FormData(suggestForm);
      return [
        '【建议类型】' + (data.get('type') || ''),
        '【页面位置】' + (data.get('location') || '未填写'),
        '【建议内容】' + (data.get('message') || ''),
        '【联系方式】' + (data.get('contact') || '未填写'),
        '',
        '页面：' + window.location.href,
      ].join('\n');
    }

    function showFallback(reason) {
      if (suggestFallbackText) {
        suggestFallbackText.textContent = reason;
      }
      var repo = (suggestDialog.dataset.repoUrl || '').replace(/\/+$/, '');
      if (suggestGithub) {
        if (repo) {
          var data = new FormData(suggestForm);
          var title = '[建议] ' + (data.get('type') || '') + ' · ' + String(data.get('message') || '').slice(0, 36);
          var body = suggestionText() + '\n\n---\n由页面建议表单生成';
          suggestGithub.href = repo + '/issues/new?title=' + encodeURIComponent(title) +
            '&body=' + encodeURIComponent(body) + '&labels=suggestion';
          suggestGithub.hidden = false;
        } else {
          suggestGithub.hidden = true;
        }
      }
      if (suggestFallback) suggestFallback.hidden = false;
    }

    suggestForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var data = new FormData(suggestForm);
      var message = String(data.get('message') || '').trim();
      var contact = String(data.get('contact') || '').trim();

      if (message.length < 10) {
        if (suggestStatus) {
          suggestStatus.textContent = '请至少填写 10 个字，说明具体问题与依据。';
          suggestStatus.className = 'form-status error';
        }
        if (messageField) messageField.focus();
        return;
      }
      if (message.length > 1000) {
        if (suggestStatus) {
          suggestStatus.textContent = '建议内容请控制在 1000 字以内。';
          suggestStatus.className = 'form-status error';
        }
        return;
      }

      lastSuggestion = {
        type: String(data.get('type') || '其他'),
        location: String(data.get('location') || '').trim(),
        message: message,
        contact: contact,
        website: String(data.get('website') || ''),
        page: window.location.href,
      };

      if (suggestStatus) {
        suggestStatus.textContent = '正在提交…';
        suggestStatus.className = 'form-status';
      }
      if (suggestSubmit) {
        suggestSubmit.disabled = true;
        suggestSubmit.textContent = '提交中…';
      }
      if (suggestFallback) suggestFallback.hidden = true;

      fetch('api/suggestions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(lastSuggestion),
      }).then(function (response) {
        var contentType = response.headers.get('content-type') || '';
        if (contentType.indexOf('application/json') === -1) {
          throw new Error('static');
        }
        return response.json().then(function (json) {
          if (!response.ok || !json.ok) throw new Error(json.error || '提交失败，请稍后再试。');
          return json;
        });
      }).then(function (json) {
        if (suggestForm) suggestForm.hidden = true;
        if (suggestReceipt) suggestReceipt.textContent = json.id;
        if (suggestSuccess) suggestSuccess.hidden = false;
        if (suggestDialog) {
          suggestDialog.classList.add('is-success');
          suggestDialog.scrollTop = 0;
        }
        if (suggestStatus) {
          suggestStatus.textContent = '';
          suggestStatus.className = 'form-status';
        }
      }).catch(function (error) {
        var isStatic = error.message === 'static';
        var isNetwork = /fetch|network|load failed/i.test(error.message);
        var friendly = isStatic
          ? '当前页面为纯静态托管，无法直接写入审核队列。'
          : isNetwork
            ? '网络暂时不可用，建议尚未提交。'
            : error.message;
        if (suggestStatus) {
          suggestStatus.textContent = friendly;
          suggestStatus.className = 'form-status error';
        }
        showFallback(isStatic
          ? '请通过 GitHub Issue 提交（公开可追踪），或复制建议内容后发送给维护者。'
          : '请重试，或通过 GitHub Issue 提交、复制建议内容后发送给维护者。');
        if (suggestSubmit) {
          suggestSubmit.disabled = false;
          suggestSubmit.textContent = '提交建议';
        }
      });
    });

    if (suggestCopy) {
      suggestCopy.addEventListener('click', function () {
        copyText(suggestionText()).then(function (ok) {
          var original = suggestCopy.textContent;
          suggestCopy.textContent = ok ? '已复制' : '复制失败';
          window.setTimeout(function () { suggestCopy.textContent = original; }, 1500);
        });
      });
    }
  }

  /* ------------------------------------------------------------ print */
  var openedForPrint = [];
  window.addEventListener('beforeprint', function () {
    $$('details').forEach(function (details) {
      if (!details.open) {
        details.open = true;
        openedForPrint.push(details);
      }
    });
  });
  window.addEventListener('afterprint', function () {
    openedForPrint.forEach(function (details) { details.open = false; });
    openedForPrint = [];
  });

  /* --------------------------------------------------------- initialise */
  revealHash();
  window.addEventListener('load', function () {
    if (window.location.hash) revealHash();
  });
})();
