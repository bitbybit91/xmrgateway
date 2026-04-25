/**
 * inject.js
 * Entry point — auto-initialises the investment-platform system on page load.
 *
 * What this script does:
 *  1. Loads payment-config.json (relative to the script's own directory).
 *  2. Instantiates PaymentScanner, XMRConverter, and PaymentOverlay.
 *  3. Scans the page for payment buttons.
 *  4. Attaches click listeners that open the overlay with the correct amount.
 *  5. Re-scans whenever the DOM changes (supports single-page apps via
 *     MutationObserver).
 *
 * Usage — add ONE script tag to any static HTML page:
 *   <script src="/path/to/inject.js" data-config="/path/to/payment-config.json"></script>
 *
 * Optional window globals (set before this script loads):
 *   window.XMR_ADDRESS  — Monero wallet address shown in the overlay.
 *   window.XMR_CONFIG   — Inline config object (overrides payment-config.json).
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Resolve paths relative to this script tag.
  // ---------------------------------------------------------------------------

  var scriptTag   = document.currentScript || _findScriptTag();
  var scriptDir   = _dirOf(scriptTag ? scriptTag.src : '');
  var configUrl   = (scriptTag && scriptTag.getAttribute('data-config')) ||
                    (scriptDir + 'payment-config.json');

  var MODULES = {
    scanner:  scriptDir + 'scanner.js',
    converter: scriptDir + 'xmr-converter.js',
    overlay:  scriptDir + 'payment-overlay.js',
    styles:   scriptDir + 'styles.css'
  };

  // ---------------------------------------------------------------------------
  // Bootstrap
  // ---------------------------------------------------------------------------

  _injectStylesheet(MODULES.styles);

  _loadScripts([MODULES.scanner, MODULES.converter, MODULES.overlay], function () {
    _loadConfig(configUrl, function (config) {
      _init(config);
    });
  });

  // ---------------------------------------------------------------------------
  // Core initialisation
  // ---------------------------------------------------------------------------

  function _init(config) {
    // Allow inline config to override file config.
    if (typeof window !== 'undefined' && window.XMR_CONFIG &&
        typeof window.XMR_CONFIG === 'object') {
      config = _merge(config, window.XMR_CONFIG);
    }

    var scanner   = new window.PaymentScanner(config);
    var converter = new window.XMRConverter(config);
    var overlay   = new window.PaymentOverlay(config, converter);

    // Pre-warm the price cache so the first click is instant.
    converter.getPrice().catch(function () {
      console.warn('[inject.js] Could not pre-warm XMR price cache.');
    });

    var attached = new (typeof WeakSet !== 'undefined' ? WeakSet : _FakeWeakSet)();

    function scanAndAttach() {
      var buttons = scanner.scan(document.body);
      buttons.forEach(function (info) {
        if (attached.has(info.element)) return;
        attached.add(info.element);
        info.element.addEventListener('click', function (e) {
          // Let the host page cancel propagation if needed; we only intercept.
          overlay.open(info);
        });
        // Mark for debugging / targeting from CSS.
        info.element.setAttribute('data-xmr-payment', 'true');
        info.element.setAttribute('data-xmr-amount', String(info.amount));
      });

      if (buttons.length) {
        console.info(
          '[inject.js] ' + buttons.length + ' payment button(s) detected.',
          buttons.map(function (b) {
            return '"' + b.label + '" → ' + b.currency + ' ' + b.amount;
          })
        );
      }
    }

    // Initial scan.
    scanAndAttach();

    // Re-scan on DOM mutations (supports SPAs / lazy-loaded content).
    if (typeof MutationObserver !== 'undefined') {
      var debounceTimer = null;
      var observer = new MutationObserver(function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(scanAndAttach, 300);
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
  }

  // ---------------------------------------------------------------------------
  // Utilities
  // ---------------------------------------------------------------------------

  function _loadConfig(url, cb) {
    // If a global config is already provided, skip the fetch.
    if (typeof window !== 'undefined' && window.XMR_CONFIG) {
      return cb(window.XMR_CONFIG);
    }
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.onload = function () {
      var cfg = {};
      if (xhr.status >= 200 && xhr.status < 300) {
        try { cfg = JSON.parse(xhr.responseText); } catch (e) {
          console.warn('[inject.js] Failed to parse config JSON:', e);
        }
      } else {
        console.warn('[inject.js] Could not load config from', url, '(HTTP', xhr.status + ').',
          'Using built-in defaults.');
      }
      cb(cfg);
    };
    xhr.onerror = function () {
      console.warn('[inject.js] Network error loading config. Using built-in defaults.');
      cb({});
    };
    xhr.send();
  }

  /**
   * Loads an array of JS URLs in order, calling `cb` when all are done.
   * Skips modules that are already present on the global object.
   */
  function _loadScripts(urls, cb) {
    var pending = [];
    var alreadyLoaded = {
      'scanner.js':   typeof window.PaymentScanner  !== 'undefined',
      'converter.js': typeof window.XMRConverter    !== 'undefined',
      'overlay.js':   typeof window.PaymentOverlay  !== 'undefined'
    };

    urls.forEach(function (url) {
      var filename = url.split('/').pop();
      if (alreadyLoaded[filename]) return;
      pending.push(url);
    });

    if (!pending.length) { cb(); return; }

    var index = 0;
    function loadNext() {
      if (index >= pending.length) { cb(); return; }
      var url    = pending[index++];
      var script = document.createElement('script');
      script.src = url;
      script.onload  = loadNext;
      script.onerror = function () {
        console.error('[inject.js] Failed to load module:', url);
        loadNext();
      };
      document.head.appendChild(script);
    }
    loadNext();
  }

  function _injectStylesheet(href) {
    if (document.querySelector('link[data-xmr-styles]')) return;
    var link = document.createElement('link');
    link.rel  = 'stylesheet';
    link.href = href;
    link.setAttribute('data-xmr-styles', 'true');
    document.head.appendChild(link);
  }

  function _dirOf(url) {
    if (!url) return './';
    var parts = url.split('?')[0].split('/');
    parts.pop();
    return parts.join('/') + '/';
  }

  function _findScriptTag() {
    var scripts = document.getElementsByTagName('script');
    for (var i = scripts.length - 1; i >= 0; i--) {
      if (scripts[i].src && scripts[i].src.indexOf('inject.js') !== -1) {
        return scripts[i];
      }
    }
    return null;
  }

  function _merge(base, override) {
    var result = {};
    var key;
    for (key in base)     { if (Object.prototype.hasOwnProperty.call(base, key))     result[key] = base[key]; }
    for (key in override) { if (Object.prototype.hasOwnProperty.call(override, key)) result[key] = override[key]; }
    return result;
  }

  /**
   * Minimal WeakSet polyfill for older browsers.
   * Only supports has() / add() — sufficient for our use case.
   */
  function _FakeWeakSet() { this._items = []; }
  _FakeWeakSet.prototype.has = function (item) { return this._items.indexOf(item) !== -1; };
  _FakeWeakSet.prototype.add = function (item) { if (!this.has(item)) this._items.push(item); };

}());
