/**
 * payment-overlay.js
 * Modal overlay injected into the page when a payment button is clicked.
 *
 * Features:
 *  • Displays the fiat amount and the live XMR equivalent.
 *  • Shows a QR-code placeholder / XMR address field (address sourced from
 *    data-xmr-address on the original button, or from window.XMR_ADDRESS).
 *  • Copy-to-clipboard for the XMR amount and address.
 *  • Keyboard-accessible (Escape closes, focus trap inside modal).
 *  • Fully self-contained; no external CSS frameworks required.
 */

(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.PaymentOverlay = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var OVERLAY_ID = 'xmr-payment-overlay';

  // ---------------------------------------------------------------------------
  // PaymentOverlay
  // ---------------------------------------------------------------------------

  /**
   * @param {object} config      — payment-config.json object.
   * @param {object} converter   — XMRConverter instance.
   */
  function PaymentOverlay(config, converter) {
    this.config    = config    || {};
    this.converter = converter || null;
    this._overlay  = null;
    this._onKeyDown = null;
  }

  /**
   * Opens the overlay for a detected payment button result.
   *
   * @param {object} buttonInfo   — item returned by PaymentScanner#scan()
   *   { element, amount, currency, tier, label }
   */
  PaymentOverlay.prototype.open = function (buttonInfo) {
    var self = this;
    self._removeExisting();

    var overlay = self._buildSkeleton(buttonInfo);
    document.body.appendChild(overlay);
    self._overlay = overlay;

    // Trap focus inside the modal.
    self._trapFocus(overlay);

    // Escape key closes the overlay.
    self._onKeyDown = function (e) {
      if (e.key === 'Escape' || e.keyCode === 27) { self.close(); }
    };
    document.addEventListener('keydown', self._onKeyDown);

    // Fetch live XMR amount and update when ready.
    if (self.converter) {
      self._updateXMRAmount(buttonInfo.amount, overlay);
    }
  };

  /**
   * Closes and removes the overlay from the DOM.
   */
  PaymentOverlay.prototype.close = function () {
    this._removeExisting();
    if (this._onKeyDown) {
      document.removeEventListener('keydown', this._onKeyDown);
      this._onKeyDown = null;
    }
  };

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  /**
   * Builds the full overlay DOM tree synchronously (with a loading state for
   * the XMR amount which is filled in once the API call resolves).
   * @private
   */
  PaymentOverlay.prototype._buildSkeleton = function (buttonInfo) {
    var self     = this;
    var config   = self.config;
    var currency = buttonInfo.currency || (config.currency || 'USD');

    var overlay = _el('div', { id: OVERLAY_ID, role: 'dialog', 'aria-modal': 'true',
      'aria-labelledby': 'xmr-overlay-title', tabindex: '-1' });

    var backdrop = _el('div', { class: 'xmr-backdrop' });
    backdrop.addEventListener('click', function () { self.close(); });
    overlay.appendChild(backdrop);

    var modal = _el('div', { class: 'xmr-modal', role: 'document' });

    // ---- Header ----
    var header = _el('div', { class: 'xmr-modal__header' });
    var title  = _el('h2',  { id: 'xmr-overlay-title', class: 'xmr-modal__title' });
    title.textContent = config.overlayTitle || 'Pay with Monero (XMR)';
    var closeBtn = _el('button', { class: 'xmr-modal__close', 'aria-label': 'Close' });
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', function () { self.close(); });
    header.appendChild(title);
    header.appendChild(closeBtn);
    modal.appendChild(header);

    // ---- Body ----
    var body = _el('div', { class: 'xmr-modal__body' });

    // Tier badge (if the amount came from a tier).
    if (buttonInfo.tier) {
      var badge = _el('div', { class: 'xmr-tier-badge' });
      badge.textContent = buttonInfo.tier.name + ' Plan';
      body.appendChild(badge);
    }

    // Fiat amount row.
    var fiatRow   = _el('div', { class: 'xmr-amount-row' });
    var fiatLabel = _el('span', { class: 'xmr-amount-row__label' });
    fiatLabel.textContent = 'Amount';
    var fiatValue = _el('span', { class: 'xmr-amount-row__value' });
    fiatValue.textContent = self.converter
      ? self.converter.formatUSD(buttonInfo.amount, currency)
      : currency + ' ' + buttonInfo.amount.toFixed(2);
    fiatRow.appendChild(fiatLabel);
    fiatRow.appendChild(fiatValue);
    body.appendChild(fiatRow);

    // XMR amount row.
    var xmrRow   = _el('div', { class: 'xmr-amount-row xmr-amount-row--xmr' });
    var xmrLabel = _el('span', { class: 'xmr-amount-row__label' });
    xmrLabel.textContent = 'XMR Equivalent';
    var xmrValue = _el('span', { class: 'xmr-amount-row__value', id: 'xmr-live-amount' });
    xmrValue.textContent = 'Fetching price…';
    var xmrCopy = _el('button', { class: 'xmr-copy-btn', 'aria-label': 'Copy XMR amount',
      id: 'xmr-copy-amount', disabled: 'true' });
    xmrCopy.textContent = 'Copy';
    xmrRow.appendChild(xmrLabel);
    xmrRow.appendChild(xmrValue);
    xmrRow.appendChild(xmrCopy);
    body.appendChild(xmrRow);

    // Exchange rate note.
    var rateNote = _el('p', { class: 'xmr-rate-note', id: 'xmr-rate-note' });
    rateNote.textContent = 'Loading live exchange rate…';
    body.appendChild(rateNote);

    // XMR address (optional).
    var address = _getXMRAddress(buttonInfo.element);
    if (address) {
      var addrBlock = _el('div', { class: 'xmr-address-block' });
      var addrLabel = _el('label', { class: 'xmr-address-block__label', 'for': 'xmr-address-field' });
      addrLabel.textContent = 'Send XMR to:';
      var addrInput = _el('input', { type: 'text', id: 'xmr-address-field',
        class: 'xmr-address-block__input', readonly: 'true', value: address });
      var addrCopy = _el('button', { class: 'xmr-copy-btn', 'aria-label': 'Copy XMR address' });
      addrCopy.textContent = 'Copy';
      addrCopy.addEventListener('click', function () { _copyText(address, addrCopy); });
      addrBlock.appendChild(addrLabel);
      addrBlock.appendChild(addrInput);
      addrBlock.appendChild(addrCopy);
      body.appendChild(addrBlock);
    }

    // ---- Footer ----
    var footer = _el('div', { class: 'xmr-modal__footer' });
    var note   = _el('p',   { class: 'xmr-modal__footnote' });
    note.textContent =
      'XMR prices update every ' +
      Math.round((self.config.priceCacheDurationMs || 60000) / 1000) +
      ' seconds. Send the exact XMR amount shown.';
    footer.appendChild(note);

    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);

    // Focus the modal for keyboard users.
    setTimeout(function () { modal.focus && modal.focus(); }, 50);

    return overlay;
  };

  /**
   * Calls the converter and populates the XMR amount fields.
   * @private
   */
  PaymentOverlay.prototype._updateXMRAmount = function (usdAmount, overlay) {
    var self = this;
    self.converter.convert(usdAmount).then(function (result) {
      var xmrAmountEl = overlay.querySelector('#xmr-live-amount');
      var rateNoteEl  = overlay.querySelector('#xmr-rate-note');
      var copyBtn     = overlay.querySelector('#xmr-copy-amount');
      var xmrStr      = self.converter.formatXMR(result.xmr);

      if (xmrAmountEl) xmrAmountEl.textContent = xmrStr;
      if (rateNoteEl) {
        rateNoteEl.textContent =
          '1 XMR = ' + self.converter.formatUSD(result.usdPerXmr) +
          ' (live rate)';
      }
      if (copyBtn) {
        copyBtn.removeAttribute('disabled');
        copyBtn.addEventListener('click', function () { _copyText(xmrStr, copyBtn); });
      }
    }).catch(function (err) {
      var xmrAmountEl = overlay.querySelector('#xmr-live-amount');
      var rateNoteEl  = overlay.querySelector('#xmr-rate-note');
      if (xmrAmountEl) xmrAmountEl.textContent = 'Price unavailable';
      if (rateNoteEl)  rateNoteEl.textContent   = 'Could not fetch live rate. Please try again.';
      console.error('[PaymentOverlay] Failed to load XMR price:', err);
    });
  };

  /** @private */
  PaymentOverlay.prototype._removeExisting = function () {
    var existing = document.getElementById(OVERLAY_ID);
    if (existing && existing.parentNode) {
      existing.parentNode.removeChild(existing);
    }
    this._overlay = null;
  };

  /**
   * Simple focus trap: cycles Tab/Shift+Tab within focusable descendants.
   * @private
   */
  PaymentOverlay.prototype._trapFocus = function (overlay) {
    overlay.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab' && e.keyCode !== 9) return;
      var focusable = Array.prototype.slice.call(
        overlay.querySelectorAll(
          'a[href], button:not([disabled]), input:not([disabled]), ' +
          'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      );
      if (!focusable.length) return;
      var first = focusable[0];
      var last  = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
      }
    });
  };

  // ---------------------------------------------------------------------------
  // Module-level helpers (no `this` needed)
  // ---------------------------------------------------------------------------

  function _el(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'class') { el.className = attrs[k]; }
        else               { el.setAttribute(k, attrs[k]); }
      });
    }
    return el;
  }

  function _copyText(text, btn) {
    var originalText = btn.textContent;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        _flashCopied(btn, originalText);
      }).catch(function () {
        _legacyCopy(text, btn, originalText);
      });
    } else {
      _legacyCopy(text, btn, originalText);
    }
  }

  function _legacyCopy(text, btn, originalText) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (_) {}
    document.body.removeChild(ta);
    _flashCopied(btn, originalText);
  }

  function _flashCopied(btn, originalText) {
    btn.textContent = 'Copied!';
    btn.classList.add('xmr-copy-btn--copied');
    setTimeout(function () {
      btn.textContent = originalText;
      btn.classList.remove('xmr-copy-btn--copied');
    }, 2000);
  }

  function _getXMRAddress(el) {
    // Check the button itself, then walk up a few ancestors.
    var node = el;
    for (var i = 0; i < 5 && node; i++) {
      var addr = node.getAttribute && (
        node.getAttribute('data-xmr-address') ||
        node.getAttribute('data-xmr') ||
        node.getAttribute('data-wallet')
      );
      if (addr && addr.length >= 95) return addr;  // Standard XMR address length.
      node = node.parentNode;
    }
    // Global fallback.
    if (typeof window !== 'undefined' && window.XMR_ADDRESS &&
        window.XMR_ADDRESS.length >= 95) {
      return window.XMR_ADDRESS;
    }
    return null;
  }

  return PaymentOverlay;
}));
