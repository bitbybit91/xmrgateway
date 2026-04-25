/**
 * scanner.js
 * DOM scanner — detects payment buttons and their associated fiat amounts.
 *
 * Detection strategy (executed in order):
 *  1. Text content matches the configured button-text regex.
 *  2. class or id attributes match the configured selector regex.
 *
 * Amount extraction strategy (executed in order):
 *  1. data-amount attribute on the element itself.
 *  2. Numeric value inside the element's text (e.g. "Buy for $499").
 *  3. Nearest ancestor/sibling that contains a currency-formatted number.
 *  4. If nothing is found, fall back to the configured default tier.
 */

(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.PaymentScanner = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Internal helpers
  // ---------------------------------------------------------------------------

  /**
   * Returns the numeric dollar amount embedded in a string, or null.
   * Handles formats: $1,234.56  |  1234.56  |  1,234  |  USD 1234
   */
  function extractAmount(text) {
    if (!text) return null;
    // Strip common currency symbols / codes, then parse the first plausible number.
    var cleaned = text.replace(/[£€¥₹₽]|USD|EUR|GBP|CAD|AUD/gi, '');
    var match = cleaned.match(/\$?\s*([\d]{1,3}(?:[,\s]?[\d]{3})*(?:\.[\d]{1,2})?)/);
    if (!match) return null;
    var num = parseFloat(match[1].replace(/[,\s]/g, ''));
    return isFinite(num) && num > 0 ? num : null;
  }

  /**
   * Walks up the DOM tree (up to maxLevels ancestors) looking for a currency
   * amount in text nodes or value attributes.
   */
  function findAmountNearby(el, maxLevels) {
    maxLevels = maxLevels || 4;
    var node = el;
    for (var level = 0; level <= maxLevels; level++) {
      if (!node || node === document.body) break;

      // Check siblings at this level.
      var sibs = node.parentNode ? Array.prototype.slice.call(node.parentNode.childNodes) : [];
      for (var i = 0; i < sibs.length; i++) {
        var sib = sibs[i];
        if (sib === node) continue;
        var amount = extractAmount(sib.textContent || sib.nodeValue || '');
        if (amount !== null) return amount;
      }

      // Check the node itself (in case the button's own text contains a price).
      var selfAmount = extractAmount(node.textContent || '');
      if (selfAmount !== null) return selfAmount;

      node = node.parentNode;
    }
    return null;
  }

  /**
   * Returns true when the element is interactive and visible.
   */
  function isUsable(el) {
    if (!el || !el.getBoundingClientRect) return false;
    var rect = el.getBoundingClientRect();
    // Allow elements that aren't rendered yet (e.g. inside a hidden modal).
    var style = window.getComputedStyle(el);
    if (style.display === 'none' && rect.width === 0) return false;
    return true;
  }

  // ---------------------------------------------------------------------------
  // PaymentScanner
  // ---------------------------------------------------------------------------

  /**
   * @param {object} config  — the parsed payment-config.json object.
   */
  function PaymentScanner(config) {
    this.config = config || {};

    var textPatternSource = (config && config.buttonTextPattern)
      ? config.buttonTextPattern
      : '(pay|invest|buy|checkout|subscribe|purchase|get\\s+started|deposit|fund|contribute)';
    var selectorPatternSource = (config && config.buttonSelectorPattern)
      ? config.buttonSelectorPattern
      : '(pay|invest|buy|checkout|cta|btn|button|action)';

    this._textRegex     = new RegExp(textPatternSource, 'i');
    this._selectorRegex = new RegExp(selectorPatternSource, 'i');
  }

  /**
   * Scans the document (or a root element) for payment buttons.
   *
   * @param {Element} [rootEl=document.body]
   * @returns {Array<{element: Element, amount: number, currency: string, tier: object|null}>}
   */
  PaymentScanner.prototype.scan = function (rootEl) {
    rootEl = rootEl || document.body;
    var self = this;
    var found = [];
    var seen  = new Set ? new Set() : { _s: [], has: function(v){ return this._s.indexOf(v) !== -1; }, add: function(v){ this._s.push(v); } };

    // Candidate tags — anything that a human might click.
    var candidates = rootEl.querySelectorAll(
      'button, a, input[type="button"], input[type="submit"], ' +
      '[role="button"], [onclick], .btn, .button, .cta'
    );

    Array.prototype.forEach.call(candidates, function (el) {
      if (seen.has(el)) return;
      if (!self._isPaymentButton(el)) return;
      seen.add(el);

      var amount   = self._resolveAmount(el);
      var currency = (self.config.currency || 'USD').toUpperCase();

      found.push({
        element:  el,
        amount:   amount.value,
        currency: currency,
        tier:     amount.tier || null,
        label:    (el.textContent || el.value || '').trim().replace(/\s+/g, ' ')
      });
    });

    return found;
  };

  /**
   * Returns true if the element looks like a payment button.
   * @private
   */
  PaymentScanner.prototype._isPaymentButton = function (el) {
    // Text match
    var text = (el.textContent || el.value || el.getAttribute('aria-label') || '').trim();
    if (this._textRegex.test(text)) return true;

    // Class / ID match
    var classList = (el.className || '').toString();
    var id        = (el.id || '');
    if (this._selectorRegex.test(classList) || this._selectorRegex.test(id)) return true;

    // name / data-action attribute match
    var name   = el.getAttribute('name')   || '';
    var action = el.getAttribute('data-action') || '';
    if (this._selectorRegex.test(name) || this._selectorRegex.test(action)) return true;

    return false;
  };

  /**
   * Resolves the dollar amount for a button.
   * Returns { value: number, tier: object|null }.
   * @private
   */
  PaymentScanner.prototype._resolveAmount = function (el) {
    // 1. data-amount attribute (highest priority).
    var dataAmount = el.getAttribute('data-amount') || el.getAttribute('data-price');
    if (dataAmount) {
      var parsed = parseFloat(dataAmount.replace(/[^0-9.]/g, ''));
      if (isFinite(parsed) && parsed > 0) {
        return { value: parsed, tier: null };
      }
    }

    // 2. Inline text of the button itself.
    var inlineAmount = extractAmount(el.textContent || el.value || '');
    if (inlineAmount !== null) {
      return { value: inlineAmount, tier: null };
    }

    // 3. Nearby DOM (siblings / ancestors).
    var nearbyAmount = findAmountNearby(el, 5);
    if (nearbyAmount !== null) {
      return { value: nearbyAmount, tier: null };
    }

    // 4. Default tier.
    return this._defaultTierAmount();
  };

  /**
   * Returns the default tier amount based on config.
   * @private
   */
  PaymentScanner.prototype._defaultTierAmount = function () {
    var tiers = (this.config.tiers && this.config.tiers.length) ? this.config.tiers : [
      { name: 'Starter', amount: 1000 }
    ];
    var idx = (typeof this.config.defaultTierIndex === 'number')
      ? this.config.defaultTierIndex
      : 0;
    idx = Math.max(0, Math.min(idx, tiers.length - 1));
    var tier = tiers[idx];
    return { value: tier.amount, tier: tier };
  };

  return PaymentScanner;
}));
