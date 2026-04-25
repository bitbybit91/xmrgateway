/**
 * xmr-converter.js
 * Live XMR price fetcher + USD → XMR conversion logic.
 *
 * Price source: CoinGecko public API (no API key required for moderate usage).
 * Results are cached in memory for `priceCacheDurationMs` milliseconds to
 * avoid hammering the price endpoint on every button click.
 *
 * For deployments behind a CORS-restricted environment, set the optional
 * `xmrPriceApiUrl` in payment-config.json to point at your own relay endpoint
 * that proxies the CoinGecko response.
 */

(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.XMRConverter = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // Default CoinGecko endpoint — returns { monero: { usd: <price> } }
  var DEFAULT_API_URL =
    'https://api.coingecko.com/api/v3/simple/price?ids=monero&vs_currencies=usd';

  // Fallback mirror in case CoinGecko is rate-limited.
  var FALLBACK_API_URL =
    'https://min-api.cryptocompare.com/data/price?fsym=XMR&tsyms=USD';

  // ---------------------------------------------------------------------------
  // XMRConverter
  // ---------------------------------------------------------------------------

  /**
   * @param {object} config  — the parsed payment-config.json object.
   */
  function XMRConverter(config) {
    this.config          = config || {};
    this.apiUrl          = (config && config.xmrPriceApiUrl) || DEFAULT_API_URL;
    this.cacheDurationMs = (config && config.priceCacheDurationMs) || 60000;
    this.precision       = (config && config.xmrPrecision != null) ? config.xmrPrecision : 6;

    this._cachedPrice    = null;   // USD price per 1 XMR
    this._cacheTimestamp = 0;      // epoch ms of last successful fetch
    this._fetchPromise   = null;   // de-duplicate concurrent requests
  }

  /**
   * Returns the current XMR/USD price.
   * Fetches from the API when the cache is stale; otherwise resolves instantly.
   *
   * @returns {Promise<number>}  USD price of 1 XMR
   */
  XMRConverter.prototype.getPrice = function () {
    var self = this;
    var now  = Date.now();

    // Cache hit.
    if (self._cachedPrice !== null && (now - self._cacheTimestamp) < self.cacheDurationMs) {
      return Promise.resolve(self._cachedPrice);
    }

    // De-duplicate concurrent callers.
    if (self._fetchPromise) {
      return self._fetchPromise;
    }

    self._fetchPromise = self._fetchPrice()
      .then(function (price) {
        self._cachedPrice    = price;
        self._cacheTimestamp = Date.now();
        self._fetchPromise   = null;
        return price;
      })
      .catch(function (err) {
        self._fetchPromise = null;
        // If we have a stale cached value, return it rather than crashing.
        if (self._cachedPrice !== null) {
          console.warn('[XMRConverter] Price fetch failed, using stale cache.', err);
          return self._cachedPrice;
        }
        return Promise.reject(err);
      });

    return self._fetchPromise;
  };

  /**
   * Converts a USD amount to XMR.
   *
   * @param {number} usdAmount
   * @returns {Promise<{xmr: number, usdPerXmr: number}>}
   */
  XMRConverter.prototype.convert = function (usdAmount) {
    return this.getPrice().then(function (usdPerXmr) {
      var xmr = usdAmount / usdPerXmr;
      return {
        xmr:       xmr,
        usdPerXmr: usdPerXmr
      };
    });
  };

  /**
   * Formats an XMR number as a human-readable string.
   *
   * @param {number} xmr
   * @param {number} [precision]
   * @returns {string}
   */
  XMRConverter.prototype.formatXMR = function (xmr, precision) {
    var p = (precision != null) ? precision : this.precision;
    return xmr.toFixed(p) + ' XMR';
  };

  /**
   * Formats a USD number as a human-readable string.
   *
   * @param {number} usd
   * @param {string} [currency='USD']
   * @returns {string}
   */
  XMRConverter.prototype.formatUSD = function (usd, currency) {
    currency = currency || (this.config.currency) || 'USD';
    try {
      return new Intl.NumberFormat('en-US', {
        style:    'currency',
        currency: currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }).format(usd);
    } catch (_) {
      return '$' + usd.toFixed(2);
    }
  };

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  /**
   * Fetches the live XMR/USD price.
   * Tries the primary URL first; falls back to CryptoCompare if it fails.
   * @private
   */
  XMRConverter.prototype._fetchPrice = function () {
    var self = this;
    return self._fetchFromUrl(self.apiUrl)
      .catch(function () {
        // Primary failed — try fallback if it differs.
        if (self.apiUrl !== FALLBACK_API_URL) {
          return self._fetchFromUrl(FALLBACK_API_URL);
        }
        return Promise.reject(new Error('All XMR price APIs failed.'));
      });
  };

  /**
   * @param {string} url
   * @returns {Promise<number>}
   * @private
   */
  XMRConverter.prototype._fetchFromUrl = function (url) {
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open('GET', url, true);
      xhr.timeout = 10000; // 10 s
      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            var data = JSON.parse(xhr.responseText);
            var price = XMRConverter._extractPrice(data);
            if (price === null) {
              reject(new Error('[XMRConverter] Unexpected API response format.'));
            } else {
              resolve(price);
            }
          } catch (e) {
            reject(e);
          }
        } else {
          reject(new Error('[XMRConverter] HTTP ' + xhr.status));
        }
      };
      xhr.onerror   = function () { reject(new Error('[XMRConverter] Network error.')); };
      xhr.ontimeout = function () { reject(new Error('[XMRConverter] Request timed out.')); };
      xhr.send();
    });
  };

  /**
   * Understands both CoinGecko and CryptoCompare response shapes.
   * @param {object} data
   * @returns {number|null}
   * @private
   * @static
   */
  XMRConverter._extractPrice = function (data) {
    // CoinGecko: { "monero": { "usd": 170.5 } }
    if (data && data.monero && typeof data.monero.usd === 'number') {
      return data.monero.usd;
    }
    // CryptoCompare: { "USD": 170.5 }
    if (data && typeof data.USD === 'number') {
      return data.USD;
    }
    return null;
  };

  return XMRConverter;
}));
