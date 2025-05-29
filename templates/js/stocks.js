let chart;
let currentSymbol = "";
let tradingViewWidget = null;

function getUrlParameter(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}

async function loadWatchlist() {
    /**
     * Loads the watchlist from the server and displays it.
     */
    try {
        const response = await fetch("/api/watchlist");
        const watchlist = await response.json();

        const watchlistDiv = document.getElementById("watchlist");
        if (watchlistDiv) {
            if (watchlist.length === 0) {
                watchlistDiv.innerHTML = `
                        <div class="text-white/60 text-sm">
                                Your watchlist is empty. Search for stocks to add them here.
                        </div>
                    `;
                return;
            }

            watchlistDiv.innerHTML = watchlist
                .map(
                    (item) => `
                        <div class="bg-white/5 backdrop-blur-xl border border-white/10 rounded-lg p-4 group">
                                <div class="flex justify-between items-center">
                                        <div>
                                                <div class="font-medium text-white">${item.symbol}</div>
                                                <div class="text-sm text-white/60">${new Date(
                                                    item.added_at
                                                ).toLocaleDateString()}</div>
                                        </div>
                                        <div class="flex items-center gap-3">
                                                <button onclick="searchStock('${
                                                    item.symbol
                                                }')" class="text-accent hover:text-accent-light transition-colors">
                                                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                                                        </svg>
                                                </button>
                                                <button onclick="removeFromWatchlist('${
                                                    item.symbol
                                                }')" class="text-red-400 hover:text-red-300 opacity-0 group-hover:opacity-100 transition-all">
                                                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                                        </svg>
                                                </button>
                                        </div>
                                </div>
                                ${item.notes ? `<div class="mt-2 text-sm text-white/60">${item.notes}</div>` : ""}
                        </div>
                        `
                )
                .join("");
        }
    } catch (error) {
        console.error("Error loading watchlist:", error);
    }
}

async function toggleWatchlist() {
    /**
     * Toggles a stock's presence in the watchlist.
     */
    const symbol = document.getElementById("stockSymbol").textContent;
    const watchlistBtn = document.getElementById("watchlistBtn");
    const watchlistIcon = document.getElementById("watchlistIcon");
    const watchlistText = document.getElementById("watchlistText");

    try {
        if (watchlistBtn.classList.contains("in-watchlist")) {
            const response = await fetch("/api/watchlist", {
                method: "DELETE",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ symbol }),
            });

            if (response.ok) {
                watchlistBtn.classList.remove("in-watchlist", "bg-accent/20", "border-accent/40");
                watchlistBtn.classList.add("bg-dark-300/50", "border-white/10");
                watchlistIcon.innerHTML =
                    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>';
                watchlistText.textContent = "Add to Watchlist";
            }
        } else {
            const response = await fetch("/api/watchlist", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ symbol }),
            });

            if (response.ok) {
                watchlistBtn.classList.add("in-watchlist", "bg-accent/20", "border-accent/40");
                watchlistBtn.classList.remove("bg-dark-300/50", "border-white/10");
                watchlistIcon.innerHTML =
                    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>';
                watchlistText.textContent = "In Watchlist";
            }
        }

        await loadWatchlist();
    } catch (error) {
        console.error("Error toggling watchlist:", error);
    }
}

async function removeFromWatchlist(symbol) {
    /**
     * Removes a stock from the watchlist.
     * @param {string} symbol The stock symbol to remove.
     */
    try {
        const response = await fetch("/api/watchlist", {
            method: "DELETE",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ symbol }),
        });

        if (response.ok) {
            await loadWatchlist();

            const currentSymbol = document.getElementById("stockSymbol").textContent;
            if (currentSymbol === symbol) {
                const watchlistBtn = document.getElementById("watchlistBtn");
                const watchlistIcon = document.getElementById("watchlistIcon");
                const watchlistText = document.getElementById("watchlistText");

                watchlistBtn.classList.remove("in-watchlist", "bg-accent/20");
                watchlistBtn.classList.add("bg-dark-300/50");
                watchlistIcon.innerHTML =
                    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>';
                watchlistText.textContent = "Add to Watchlist";
            }
        }
    } catch (error) {
        console.error("Error removing from watchlist:", error);
    }
}

async function searchStock(manualSymbol) {
    /**
     * Searches for a stock and displays its data.
     * @param {string} manualSymbol Optional stock symbol to search for.
     */
    setLoading(true);
    const symbol =
        manualSymbol || document.getElementById("stockSearch").value.trim().toUpperCase();
    if (!symbol || symbol === "NONE" || symbol.toLowerCase() === "none") {
        if (manualSymbol || document.activeElement === document.getElementById("stockSearch")) {
            showError("Please enter a stock symbol");
        }
        setLoading(false);
        return;
    }

    try {
        const response = await fetch(`/api/stock/${symbol}`);
        const data = await response.json();

        if (!response.ok) {
            if (data.suggestions) {
                showSuggestions(data.suggestions, symbol);
            }
            throw new Error(data.error || "Failed to fetch stock data");
        }

        const elements = {
            symbol: document.getElementById("stockSymbol"),
            name: document.getElementById("stockName"),
            price: document.getElementById("stockPrice"),
            change: document.getElementById("stockChange"),
            volume: document.getElementById("volume"),
            dayHigh: document.getElementById("dayHigh"),
            dayLow: document.getElementById("dayLow"),
            watchlistBtn: document.getElementById("watchlistBtn"),
            chatLink: document.getElementById("chatLink")
        };

        const requiredElements = ["symbol", "name", "price", "change", "volume"];
        const missingElements = requiredElements.filter((key) => !elements[key]);

        if (missingElements.length > 0) {
            throw new Error(`Missing required elements: ${missingElements.join(", ")}`);
        }

        if (elements.chatLink) {
            elements.chatLink.href = `/chat?symbol=${data.symbol}`;
        }
        
        document.querySelector('.stock-name-text').textContent = data.name;
        
        if (data.is_crypto && data.display_symbol) {
            elements.symbol.textContent = `${data.exchange}:${data.display_symbol}`;
        } else {
            elements.symbol.textContent = data.symbol;
        }
        
        elements.price.textContent = '';
        animateValue(elements.price, 0, data.price, 1000);

        const changeValue = (data.change * 100).toFixed(2);
        const isPositive = data.change >= 0;
        elements.change.innerHTML = `
            <span class="${isPositive ? 'text-accent' : 'text-red-500'}">
                ${isPositive ? "+" : ""}${changeValue}%
            </span>
            <svg class="w-5 h-5 ml-1 ${isPositive ? 'text-accent' : 'text-red-500'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                    d="${isPositive 
                        ? 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' 
                        : 'M13 17h8m0 0v-8m0 8l-8-8-4 4-6-6'}">
                </path>
            </svg>
        `;

        elements.volume.textContent = formatNumber(data.volume);

        if (elements.dayHigh && elements.dayLow) {
            elements.dayHigh.textContent = `$${data.dayHigh.toFixed(2)}`;
            elements.dayLow.textContent = `$${data.dayLow.toFixed(2)}`;
            
            const range = data.dayHigh - data.dayLow;
            const position = ((data.price - data.dayLow) / range) * 100;
            document.getElementById('currentPriceMarker').style.left = `${position}%`;
        }

        if (elements.watchlistBtn) {
            elements.watchlistBtn.classList.remove("hidden");
            const watchlistResponse = await fetch("/api/watchlist");
            const watchlist = await watchlistResponse.json();
            const inWatchlist = watchlist.some((item) => item.symbol === data.symbol);
            updateWatchlistButton(elements.watchlistBtn, inWatchlist);
        }

        showStockResult();
        hideSuggestions();
        
        let chartSymbol;
        if (data.symbol === 'BTC') {
            chartSymbol = 'BINANCE:BTCUSDT';
        } else if (data.is_crypto && data.display_symbol) {
            chartSymbol = `${data.exchange}:${data.display_symbol}`;
        } else if (data.is_crypto) {
            chartSymbol = `${data.exchange}:${data.symbol}`;
        } else {
            chartSymbol = data.symbol;
        }
        
        updateChartForStock(chartSymbol);
        
    } catch (error) {
        console.error("Error:", error);
        showError(error.message);
        hideStockResult();
    } finally {
        setLoading(false);
    }
}

function showError(message) {
    /**
     * Displays an error message on the screen.
     * @param {string} message The error message to display.
     */
    const errorDiv = document.createElement("div");
    errorDiv.className =
        "fixed top-4 right-4 bg-red-500/90 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center gap-2 animate-fade-in";
    errorDiv.innerHTML = `
        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
        </svg>
        <span>${message}</span>
    `;
    document.body.appendChild(errorDiv);

    setTimeout(() => {
        errorDiv.classList.add("opacity-0", "transition-opacity");
        setTimeout(() => errorDiv.remove(), 300);
    }, 3000);
}

function formatNumber(value) {
    /**
     * Formats a number with commas.
     * @param {number} value The number to format.
     * @returns {string} The formatted number string.
     */
    return new Intl.NumberFormat().format(value);
}

function updateWatchlistButton(button, inWatchlist) {
    /**
     * Updates the watchlist button's appearance based on whether the stock is in the watchlist.
     * @param {HTMLElement} button The watchlist button element.
     * @param {boolean} inWatchlist Whether the stock is in the watchlist.
     */
    const icon = button.querySelector("#watchlistIcon");
    const text = button.querySelector("#watchlistText");

    if (inWatchlist) {
        button.classList.add("in-watchlist", "bg-accent/20", "border-accent/40");
        button.classList.remove("bg-dark-300/50", "border-white/10");
        icon.innerHTML =
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>';
        text.textContent = "In Watchlist";
    } else {
        button.classList.remove("in-watchlist", "bg-accent/20", "border-accent/40");
        button.classList.add("bg-dark-300/50", "border-white/10");
        icon.innerHTML =
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>';
        text.textContent = "Add to Watchlist";
    }
}

function setLoading(isLoading) {
    /**
     * Sets the loading state of the search button.
     * @param {boolean} isLoading Whether to show the loading state.
     */
    const searchBtn = document.querySelector('button[onclick^="searchStock"]');
    const searchSpinner = document.getElementById('searchSpinner');
    
    if (!searchBtn || !searchSpinner) return;
    
    const btnContent = searchBtn.querySelector('.relative');
    
    if (isLoading) {
        searchBtn.disabled = true;
        searchSpinner.classList.remove('hidden');
        if (btnContent) btnContent.classList.add('opacity-0');
    } else {
        searchBtn.disabled = false;
        searchSpinner.classList.add('hidden');
        if (btnContent) btnContent.classList.remove('opacity-0');
    }
}

function animateValue(element, start, end, duration) {
    /**
     * Animates the change in value of an HTML element.
     * @param {HTMLElement} element The HTML element to animate.
     * @param {number} start The starting value.
     * @param {number} end The ending value.
     * @param {number} duration The duration of the animation in milliseconds.
     */
    const startTime = performance.now();
    const updateNumber = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const easing = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
        
        const value = start + (end - start) * easing;
        element.textContent = typeof end === 'number' ? 
            `$${value.toFixed(2)}` : formatNumber(Math.round(value));
        
        if (progress < 1) {
            requestAnimationFrame(updateNumber);
        }
    };
    requestAnimationFrame(updateNumber);
}

function initChart() {
    /**
     * Initializes the TradingView chart widget.
     */
    const chartElement = document.getElementById('tradingview_widget');
    if (!chartElement) return;
    
    if (tradingViewWidget) {
        chartElement.innerHTML = '';
    }
    
    try {
        if (typeof TradingView === 'undefined') {
            console.error('TradingView library not loaded');
            showError('Chart library could not be loaded. Please refresh the page and try again.');
            return;
        }
        
        let tvSymbol = currentSymbol;
        
        if (!tvSymbol.includes(':')) {
            const commonCryptos = ['BTC', 'ETH', 'XRP', 'LTC', 'BCH', 'ADA', 'DOT', 'LINK', 'XLM', 'DOGE', 'UNI', 'SOL', 
                                 'AVAX', 'MATIC', 'LUNA', 'SHIB', 'ATOM', 'ALGO', 'XTZ', 'FIL', 'VET', 'EOS', 'AAVE', 'MKR', 'COMP'];
            const isCrypto = commonCryptos.includes(tvSymbol) || 
                            tvSymbol.endsWith('USDT') || 
                            tvSymbol.endsWith('USD') || 
                            tvSymbol.endsWith('BTC') || 
                            tvSymbol.endsWith('ETH');
                            
            if (isCrypto) {
                if (tvSymbol === 'BTC') {
                    tvSymbol = 'BINANCE:BTCUSDT';
                } else if (commonCryptos.includes(tvSymbol) && 
                    !tvSymbol.endsWith('USDT') && 
                    !tvSymbol.endsWith('USD') && 
                    !tvSymbol.endsWith('BTC')) {
                    tvSymbol = `BINANCE:${tvSymbol}USDT`;
                } else {
                    tvSymbol = `BINANCE:${tvSymbol}`;
                }
            } else {
                tvSymbol = `NASDAQ:${tvSymbol}`;
                
                const nyseStocks = ['JPM', 'V', 'WMT', 'DIS', 'KO'];
                if (nyseStocks.includes(tvSymbol)) {
                    tvSymbol = `NYSE:${tvSymbol}`;
                }
            }
        }
        
        tradingViewWidget = new TradingView.widget({
            autosize: true,
            symbol: tvSymbol,
            interval: 'D',
            timezone: 'Etc/UTC',
            theme: 'dark',
            style: '1',
            locale: 'en',
            toolbar_bg: 'rgba(30, 40, 54, 0.8)',
            enable_publishing: false,
            hide_top_toolbar: false,
            hide_legend: false,
            save_image: false,
            container_id: 'tradingview_widget',
            studies: [
                'MASimple@tv-basicstudies',
                'RSI@tv-basicstudies',
                'Volume@tv-basicstudies'
            ],
            loading_screen: {
                backgroundColor: "rgba(30, 40, 54, 0.8)",
                foregroundColor: "#4ade80"
            }
        });
        
        chart = tradingViewWidget;
        
    } catch (error) {
        console.error('Error initializing TradingView chart:', error);
        showError('Could not initialize chart. Please try a different stock or refresh the page.');
    }
}

function updateChartForStock(symbol) {
    /**
     * Updates the chart to display the given stock symbol.
     * @param {string} symbol The stock symbol to display.
     */
    if (!symbol) return;
    
    if (symbol === 'BTC') {
        symbol = 'BINANCE:BTCUSDT';
    }
    
    currentSymbol = symbol;
    
    document.getElementById('chartSection').classList.remove('hidden');
    initChart();
}

function stopChartUpdates() {
    /**
     * Stops chart updates and resets the current symbol.
     */
    currentSymbol = "";
}

function showStockResult() {
    /**
     * Shows the stock result section with animation.
     */
    const stockResult = document.getElementById("stockResult");
    stockResult.classList.remove("hidden");
    setTimeout(() => {
        stockResult.classList.remove("opacity-0", "scale-95");
    }, 10);
    
    setTimeout(() => {
        document.querySelectorAll('.animate-number-enter').forEach(el => {
            el.classList.remove('animate-number-enter');
        });
    }, 800);
}

function hideStockResult() {
    /**
     * Hides the stock result section with animation.
     */
    const stockResult = document.getElementById("stockResult");
    stockResult.classList.add("opacity-0", "scale-95");
    setTimeout(() => {
        stockResult.classList.add("hidden");
        document.querySelectorAll('.animate-number').forEach(el => {
            el.classList.add('animate-number-enter');
        });
    }, 300);
    
    document.getElementById('chartSection').classList.add('hidden');
    stopChartUpdates();
}

function prioritizeSuggestions(suggestions) {
  /**
   * Sorts suggestions to prioritize the most popular versions of each symbol.
   * @param {Array<Object>} suggestions An array of suggestion objects.
   * @returns {Array<Object>} The sorted array of suggestions.
   */
  const popularVersions = {
    BTC: [{ symbol: "BTCUSD", exchange: "BINANCE", name: "Bitcoin USD", type: "crypto", screener: "crypto" }],
    ETH: [{ symbol: "ETHUSD", exchange: "BINANCE", name: "Ethereum USD", type: "crypto", screener: "crypto" }],
    XRP: [{ symbol: "XRPUSD", exchange: "BINANCE", name: "Ripple USD", type: "crypto", screener: "crypto" }],
    SOL: [{ symbol: "SOLUSD", exchange: "BINANCE", name: "Solana USD", type: "crypto", screener: "crypto" }],
    DOGE: [{ symbol: "DOGEUSD", exchange: "BINANCE", name: "Dogecoin USD", type: "crypto", screener: "crypto" }],
    ADA: [{ symbol: "ADAUSD", exchange: "BINANCE", name: "Cardano USD", type: "crypto", screener: "crypto" }],
    DOT: [{ symbol: "DOTUSD", exchange: "BINANCE", name: "Polkadot USD", type: "crypto", screener: "crypto" }],
    AVAX: [{ symbol: "AVAXUSD", exchange: "BINANCE", name: "Avalanche USD", type: "crypto", screener: "crypto" }],
    MATIC: [{ symbol: "MATICUSD", exchange: "BINANCE", name: "Polygon USD", type: "crypto", screener: "crypto" }],
    LINK: [{ symbol: "LINKUSD", exchange: "BINANCE", name: "Chainlink USD", type: "crypto", screener: "crypto" }],
    UNI: [{ symbol: "UNIUSD", exchange: "BINANCE", name: "Uniswap USD", type: "crypto", screener: "crypto" }],
    SHIB: [{ symbol: "SHIBUSD", exchange: "BINANCE", name: "Shiba Inu USD", type: "crypto", screener: "crypto" }],
    LTC: [{ symbol: "LTCUSD", exchange: "BINANCE", name: "Litecoin USD", type: "crypto", screener: "crypto" }],
    BCH: [{ symbol: "BCHUSD", exchange: "BINANCE", name: "Bitcoin Cash USD", type: "crypto", screener: "crypto" }],
    ATOM: [{ symbol: "ATOMUSD", exchange: "BINANCE", name: "Cosmos USD", type: "crypto", screener: "crypto" }],
    XLM: [{ symbol: "XLMUSD", exchange: "BINANCE", name: "Stellar USD", type: "crypto", screener: "crypto" }],
    ALGO: [{ symbol: "ALGOUSD", exchange: "BINANCE", name: "Algorand USD", type: "crypto", screener: "crypto" }],
    FIL: [{ symbol: "FILUSD", exchange: "BINANCE", name: "Filecoin USD", type: "crypto", screener: "crypto" }],
    ETC: [{ symbol: "ETCUSD", exchange: "BINANCE", name: "Ethereum Classic USD", type: "crypto", screener: "crypto" }],
    NEAR: [{ symbol: "NEARUSD", exchange: "BINANCE", name: "NEAR Protocol USD", type: "crypto", screener: "crypto" }],

    AAPL: [{ symbol: "AAPL", exchange: "NASDAQ", name: "Apple Inc.", searchTerms: ["apple"] }],
    MSFT: [{ symbol: "MSFT", exchange: "NASDAQ", name: "Microsoft Corporation", searchTerms: ["microsoft"] }],
    GOOGL: [{ symbol: "GOOGL", exchange: "NASDAQ", name: "Alphabet Inc.", searchTerms: ["google", "alphabet"] }],
    GOOG: [{ symbol: "GOOG", exchange: "NASDAQ", name: "Alphabet Inc. Class C", searchTerms: ["google", "alphabet"] }],
    AMZN: [{ symbol: "AMZN", exchange: "NASDAQ", name: "Amazon.com, Inc.", searchTerms: ["amazon"] }],
    TSLA: [{ symbol: "TSLA", exchange: "NASDAQ", name: "Tesla, Inc.", searchTerms: ["tesla"] }],
    META: [{ symbol: "META", exchange: "NASDAQ", name: "Meta Platforms, Inc.", searchTerms: ["facebook", "meta"] }],
    NVDA: [{ symbol: "NVDA", exchange: "NASDAQ", name: "NVIDIA Corporation", searchTerms: ["nvidia"] }],
    NFLX: [{ symbol: "NFLX", exchange: "NASDAQ", name: "Netflix, Inc.", searchTerms: ["netflix"] }],
    INTC: [{ symbol: "INTC", exchange: "NASDAQ", name: "Intel Corporation", searchTerms: ["intel"] }],
    AMD: [{ symbol: "AMD", exchange: "NASDAQ", name: "Advanced Micro Devices, Inc.", searchTerms: ["amd"] }],
    CRM: [{ symbol: "CRM", exchange: "NYSE", name: "Salesforce, Inc.", searchTerms: ["salesforce"] }],
    CSCO: [{ symbol: "CSCO", exchange: "NASDAQ", name: "Cisco Systems, Inc.", searchTerms: ["cisco"] }],
    ORCL: [{ symbol: "ORCL", exchange: "NYSE", name: "Oracle Corporation", searchTerms: ["oracle"] }],
    IBM: [{ symbol: "IBM", exchange: "NYSE", name: "International Business Machines", searchTerms: ["ibm"] }],
    ADBE: [{ symbol: "ADBE", exchange: "NASDAQ", name: "Adobe Inc.", searchTerms: ["adobe"] }],
    PYPL: [{ symbol: "PYPL", exchange: "NASDAQ", name: "PayPal Holdings, Inc.", searchTerms: ["paypal"] }],
    QCOM: [{ symbol: "QCOM", exchange: "NASDAQ", name: "Qualcomm Incorporated", searchTerms: ["qualcomm"] }],
    TXN: [{ symbol: "TXN", exchange: "NASDAQ", name: "Texas Instruments Incorporated", searchTerms: ["texas instruments"] }],

    JPM: [{ symbol: "JPM", exchange: "NYSE", name: "JPMorgan Chase & Co.", searchTerms: ["jpmorgan", "chase"] }],
    BAC: [{ symbol: "BAC", exchange: "NYSE", name: "Bank of America Corporation", searchTerms: ["bank of america"] }],
    WFC: [{ symbol: "WFC", exchange: "NYSE", name: "Wells Fargo & Company", searchTerms: ["wells fargo"] }],
    C: [{ symbol: "C", exchange: "NYSE", name: "Citigroup Inc.", searchTerms: ["citi", "citigroup", "citibank"] }],
    GS: [{ symbol: "GS", exchange: "NYSE", name: "The Goldman Sachs Group, Inc.", searchTerms: ["goldman", "goldman sachs"] }],
    MS: [{ symbol: "MS", exchange: "NYSE", name: "Morgan Stanley", searchTerms: ["morgan"] }],
    V: [{ symbol: "V", exchange: "NYSE", name: "Visa Inc.", searchTerms: ["visa", "visa inc"] }],
    MA: [{ symbol: "MA", exchange: "NYSE", name: "Mastercard Incorporated", searchTerms: ["mastercard", "master card"] }],
    AXP: [{ symbol: "AXP", exchange: "NYSE", name: "American Express Company", searchTerms: ["american express", "amex"] }],

    JNJ: [{ symbol: "JNJ", exchange: "NYSE", name: "Johnson & Johnson", searchTerms: ["johnson"] }],
    PFE: [{ symbol: "PFE", exchange: "NYSE", name: "Pfizer Inc.", searchTerms: ["pfizer"] }],
    ABBV: [{ symbol: "ABBV", exchange: "NYSE", name: "AbbVie Inc.", searchTerms: ["abbvie"] }],
    MRK: [{ symbol: "MRK", exchange: "NYSE", name: "Merck & Co., Inc.", searchTerms: ["merck"] }],
    UNH: [{ symbol: "UNH", exchange: "NYSE", name: "UnitedHealth Group Incorporated", searchTerms: ["unitedhealth", "united health"] }],
    BMY: [{ symbol: "BMY", exchange: "NYSE", name: "Bristol-Myers Squibb Company", searchTerms: ["bristol", "squibb"] }],
    TMO: [{ symbol: "TMO", exchange: "NYSE", name: "Thermo Fisher Scientific Inc.", searchTerms: ["thermo", "fisher"] }],
    ABT: [{ symbol: "ABT", exchange: "NYSE", name: "Abbott Laboratories", searchTerms: ["abbott"] }],

    KO: [{ symbol: "KO", exchange: "NYSE", name: "The Coca-Cola Company", searchTerms: ["coca", "cola", "coke"] }],
    PEP: [{ symbol: "PEP", exchange: "NASDAQ", name: "PepsiCo, Inc.", searchTerms: ["pepsi", "pepsico"] }],
    MCD: [{ symbol: "MCD", exchange: "NYSE", name: "McDonald's Corporation", searchTerms: ["mcdonald", "mcdonalds"] }],
    NKE: [{ symbol: "NKE", exchange: "NYSE", name: "NIKE, Inc.", searchTerms: ["nike"] }],
    WMT: [{ symbol: "WMT", exchange: "NYSE", name: "Walmart Inc.", searchTerms: ["walmart", "wal-mart"] }],
    PG: [{ symbol: "PG", exchange: "NYSE", name: "The Procter & Gamble Company", searchTerms: ["procter", "gamble", "p&g"] }],
    COST: [{ symbol: "COST", exchange: "NASDAQ", name: "Costco Wholesale Corporation", searchTerms: ["costco"] }],
    HD: [{ symbol: "HD", exchange: "NYSE", name: "The Home Depot, Inc.", searchTerms: ["home depot"] }],
    DIS: [{ symbol: "DIS", exchange: "NYSE", name: "The Walt Disney Company", searchTerms: ["disney", "walt"] }],

    XOM: [{ symbol: "XOM", exchange: "NYSE", name: "Exxon Mobil Corporation", searchTerms: ["exxon", "mobil"] }],
    CVX: [{ symbol: "CVX", exchange: "NYSE", name: "Chevron Corporation", searchTerms: ["chevron"] }],
    COP: [{ symbol: "COP", exchange: "NYSE", name: "ConocoPhillips", searchTerms: ["conoco", "phillips"] }],
    BP: [{ symbol: "BP", exchange: "NYSE", name: "BP p.l.c.", searchTerms: ["british petroleum"] }],
    SHEL: [{ symbol: "SHEL", exchange: "NYSE", name: "Shell plc", searchTerms: ["shell"] }],

    VZ: [{ symbol: "VZ", exchange: "NYSE", name: "Verizon Communications Inc.", searchTerms: ["verizon"] }],
    T: [{ symbol: "T", exchange: "NYSE", name: "AT&T Inc.", searchTerms: ["at&t"] }],

    "BRK.A": [{ symbol: "BRK.A", exchange: "NYSE", name: "Berkshire Hathaway Inc.", searchTerms: ["berkshire", "buffett"] }],
    "BRK.B": [{ symbol: "BRK.B", exchange: "NYSE", name: "Berkshire Hathaway Inc.", searchTerms: ["berkshire", "buffett"] }],
    BABA: [{ symbol: "BABA", exchange: "NYSE", name: "Alibaba Group Holding Limited", searchTerms: ["alibaba"] }],
    TSM: [{ symbol: "TSM", exchange: "NYSE", name: "Taiwan Semiconductor Manufacturing Company", searchTerms: ["taiwan", "semiconductor"] }],
    SHOP: [{ symbol: "SHOP", exchange: "NYSE", name: "Shopify Inc.", searchTerms: ["shopify"] }],
    SE: [{ symbol: "SE", exchange: "NYSE", name: "Sea Limited", searchTerms: ["sea"] }],
    TCEHY: [{ symbol: "TCEHY", exchange: "OTC", name: "Tencent Holdings Limited", searchTerms: ["tencent"] }],
    UBER: [{ symbol: "UBER", exchange: "NYSE", name: "Uber Technologies, Inc.", searchTerms: ["uber"] }],
    ABNB: [{ symbol: "ABNB", exchange: "NASDAQ", name: "Airbnb, Inc.", searchTerms: ["airbnb"] }],
    ZM: [{ symbol: "ZM", exchange: "NASDAQ", name: "Zoom Video Communications, Inc.", searchTerms: ["zoom"] }],
    SQ: [{ symbol: "SQ", exchange: "NYSE", name: "Block, Inc.", searchTerms: ["square", "block"] }],
    PLTR: [{ symbol: "PLTR", exchange: "NYSE", name: "Palantir Technologies Inc.", searchTerms: ["palantir"] }],
    GME: [{ symbol: "GME", exchange: "NYSE", name: "GameStop Corp.", searchTerms: ["gamestop"] }],
    AMC: [{ symbol: "AMC", exchange: "NYSE", name: "AMC Entertainment Holdings, Inc.", searchTerms: ["amc"] }],
  };

  let searchTerm = "";

  if (typeof suggestions === "object" && !Array.isArray(suggestions) && suggestions.query) {
    searchTerm = suggestions.query.toUpperCase();
  }

  if (!searchTerm && Array.isArray(suggestions) && suggestions.searchTerm) {
    searchTerm = suggestions.searchTerm.toUpperCase();
  }

  if (!searchTerm && suggestions.length > 0) {
    searchTerm = (suggestions[0].symbol || suggestions[0].name || "").toUpperCase();
  }

  if (!searchTerm) {
    console.error("Could not determine a search term for prioritization.");
    return Array.isArray(suggestions) ? suggestions : [];
  }

  const potentialMatches = [];
  const termMatches = [];
  const exactTermMatches = [];

  Object.keys(popularVersions).forEach((key) => {
    const item = popularVersions[key][0];

    item.isPreferredMatch = false;
    item.isExactTermMatch = false;

    const exactSymbolMatch = key === searchTerm || (searchTerm.length === 1 && key === searchTerm);

    const strongMatch = key.includes(searchTerm) || (item.name && item.name.toUpperCase().includes(searchTerm));

    const matchInSuggestions = suggestions.some((s) => {
      const symbolMatch = s.symbol && (s.symbol === key || s.symbol.toUpperCase().includes(key) || key.includes(s.symbol.toUpperCase()));

      const nameMatch = s.name && (s.name.toUpperCase().includes(key.toUpperCase()) || item.name.toUpperCase().includes(s.name.toUpperCase()));

      return symbolMatch || nameMatch;
    });

    const isExactTermMatch =
      searchTerm &&
      (exactSymbolMatch ||
        (item.searchTerms && item.searchTerms.some((term) => term.toLowerCase() === searchTerm.toLowerCase())));

    const searchTermMatch =
      searchTerm &&
      (strongMatch ||
        (item.searchTerms &&
          item.searchTerms.some(
            (term) => term.toLowerCase().includes(searchTerm.toLowerCase()) || searchTerm.toLowerCase().includes(term.toLowerCase())
          )));

    if (key.length === 1 && key === searchTerm) {
      exactTermMatches.push(key);
    } else if (isExactTermMatch) {
      exactTermMatches.push(key);
    }

    if (strongMatch || (searchTermMatch && matchInSuggestions)) {
      termMatches.push(key);
    }

    if (matchInSuggestions) {
      potentialMatches.push(key);
    }
  });

  const allMatches = [...new Set([...exactTermMatches, ...termMatches, ...potentialMatches])];

  const relevantMatches = allMatches.filter((key) => {
    const item = popularVersions[key][0];

    if (searchTerm.length === 1) {
      return (
        key === searchTerm ||
        key.startsWith(searchTerm) ||
        (item.searchTerms && item.searchTerms.some((term) => term.startsWith(searchTerm.toLowerCase())))
      );
    }

    const relevanceCheck =
      key.includes(searchTerm) ||
      item.name.toUpperCase().includes(searchTerm) ||
      (item.searchTerms &&
        item.searchTerms.some(
          (term) => term.toLowerCase().includes(searchTerm.toLowerCase()) || searchTerm.toLowerCase().includes(term.toLowerCase())
        ));

    return relevanceCheck;
  });

  let suggestionsArray = Array.isArray(suggestions) ? [...suggestions] : [];

  relevantMatches.forEach((key) => {
    const preferredVersion = popularVersions[key][0];
    const existingIndex = suggestionsArray.findIndex((s) => s.symbol === preferredVersion.symbol && s.exchange === preferredVersion.exchange);

    if (existingIndex === -1) {
      preferredVersion.isPreferredMatch = true;
      if (exactTermMatches.includes(key)) {
        preferredVersion.isExactTermMatch = true;
      }
      suggestionsArray.unshift(preferredVersion);
    } else {
      suggestionsArray[existingIndex].isPreferredMatch = true;
      if (exactTermMatches.includes(key)) {
        suggestionsArray[existingIndex].isExactTermMatch = true;
      }
    }
  });

  const sortedSuggestions = suggestionsArray.sort((a, b) => {
    const scoreA = (a.isExactTermMatch ? 100 : 0) + (a.isPreferredMatch ? 50 : 0);
    const scoreB = (b.isExactTermMatch ? 100 : 0) + (b.isPreferredMatch ? 50 : 0);

    if (scoreA !== scoreB) {
      return scoreB - scoreA;
    }

    const baseSymbolA = a.symbol ? a.symbol.split(":").pop().replace(/USD$|USDT$/, "") : "";
    const baseSymbolB = b.symbol ? b.symbol.split(":").pop().replace(/USD$|USDT$/, "") : "";

    if (baseSymbolA === searchTerm && baseSymbolB !== searchTerm) return -1;
    if (baseSymbolB === searchTerm && baseSymbolA !== searchTerm) return 1;

    const aNameMatch = a.name && a.name.toUpperCase().includes(searchTerm);
    const bNameMatch = b.name && b.name.toUpperCase().includes(searchTerm);
    if (aNameMatch && !bNameMatch) return -1;
    if (bNameMatch && !aNameMatch) return 1;

    const aIsListedPopular = popularVersions[baseSymbolA] !== undefined;
    const bIsListedPopular = popularVersions[baseSymbolB] !== undefined;

    const aIsPreferred = Object.keys(popularVersions).some((key) => {
      const preferred = popularVersions[key][0];
      return preferred.symbol === a.symbol && preferred.exchange === a.exchange;
    });
    const bIsPreferred = Object.keys(popularVersions).some((key) => {
      const preferred = popularVersions[key][0];
      return preferred.symbol === b.symbol && preferred.exchange === b.exchange;
    });

    if (aIsPreferred && !bIsPreferred) return -1;
    if (bIsPreferred && !aIsPreferred) return 1;

    if (aIsListedPopular && !bIsListedPopular) return -1;
    if (bIsListedPopular && !aIsListedPopular) return 1;

    if (a.type === "crypto" && a.symbol?.includes("USD") && !(b.type === "crypto" && b.symbol?.includes("USD"))) {
      return -1;
    }
    if (b.type === "crypto" && b.symbol?.includes("USD") && !(a.type === "crypto" && a.symbol?.includes("USD"))) {
      return 1;
    }

    return 0;
  });

  return sortedSuggestions;
}

function showSuggestions(suggestions, query = "") {
  /**
   * Displays stock suggestions in the suggestion div.
   * @param {Array<Object>} suggestions - An array of suggestion objects with symbol and name properties.
   * @param {string} query - The original search query entered by the user.
   */
  const suggestionsDiv = document.getElementById("stockSuggestions");
  if (!suggestionsDiv) {
    console.error("Stock suggestions div not found");
    return;
  }

  if (suggestions.length === 0) {
    hideSuggestions();
    return;
  }

  if (query) {
    suggestions.query = query;
  }

  const prioritizedSuggestions = prioritizeSuggestions(suggestions);

  suggestionsDiv.innerHTML = prioritizedSuggestions
    .map(
      (suggestion) => `
                <div class="suggestion p-3 hover:bg-accent/10 cursor-pointer transition-colors duration-200 border-b border-accent/10 last:border-0" 
                    onclick="selectSuggestion('${suggestion.symbol}')">
                        <div class="font-medium text-accent">${suggestion.symbol}</div>
                        <div class="text-sm text-white/60">${suggestion.name}</div>
                </div>
        `
    )
    .join("");

  suggestionsDiv.classList.remove("hidden");
  suggestionsDiv.classList.add("flex", "flex-col", "max-h-80", "overflow-y-auto");
  suggestionsDiv.style.display = "block";
}

function hideSuggestions() {
    /**
     * Hides the stock suggestions div.
     */
    const suggestionsDiv = document.getElementById("stockSuggestions");
    if (suggestionsDiv) {
        suggestionsDiv.classList.add("hidden");
    }
}

function selectSuggestion(symbol) {
    /**
     * Selects a suggestion and populates the search input with the selected symbol.
     * @param {string} symbol The selected stock symbol.
     */
    const searchInput = document.getElementById("stockSearch");
    if (searchInput) {
        const plainSymbol = symbol.includes(':') ? symbol.split(':')[1] : symbol;
        searchInput.value = plainSymbol;
        searchStock();
        hideSuggestions();
    }
}

function debounce(func, wait) {
    /**
     * Debounces a function to prevent it from being called too frequently.
     * @param {Function} func The function to debounce.
     * @param {number} wait The delay in milliseconds.
     * @returns {Function} The debounced function.
     */
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

window.searchStock = searchStock;
window.removeFromWatchlist = removeFromWatchlist;
window.selectSuggestion = selectSuggestion;
window.toggleWatchlist = toggleWatchlist;
window.loadWatchlist = loadWatchlist;

document.addEventListener("DOMContentLoaded", () => {
    const stockResult = document.getElementById("stockResult");
    const searchInput = document.getElementById("stockSearch");

    if (searchInput && searchInput.value === "None") {
        searchInput.value = "";
    }

    const initialSymbol = getUrlParameter("symbol");
    if (initialSymbol && initialSymbol.toLowerCase() !== "none") {
        searchInput.value = initialSymbol;
        setTimeout(() => {
            searchStock(initialSymbol);
        }, 100);
    }

    if (stockResult) {
        stockResult.addEventListener("transitionend", () => {
            if (!stockResult.classList.contains("hidden")) {
                stockResult.classList.remove("opacity-0", "translate-y-4");
            }
        });
    }

    if (searchInput) {
        const debouncedSuggest = debounce((query) => {
            if (query.length > 0 && query !== "None") {
                fetch(`/api/stock/suggest/${query}`)
                    .then((response) => response.json())
                    .then((suggestions) => {
                        showSuggestions(suggestions, query);
                    })
                    .catch((error) => {
                        console.error("Error fetching suggestions:", error);
                    });
            } else {
                hideSuggestions();
            }
        }, 300);

        searchInput.addEventListener("input", (e) => {
            const query = e.target.value.trim();
            if (query && query !== "None") {
                debouncedSuggest(query);
            } else {
                hideSuggestions();
            }
        });

        searchInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                searchStock();
            }
        });
        
        VanillaTilt.init(document.querySelectorAll(".tilt-card"), {
            max: 5,
            speed: 400,
            glare: true,
            "max-glare": 0.2,
            scale: 1.02,
        });
    }

    const userAuthenticated = document.body.getAttribute('data-user-authenticated') === 'true';
    if (userAuthenticated) {
        loadWatchlist();
    }
});

document.addEventListener("click", (event) => {
    const suggestionsDiv = document.getElementById("stockSuggestions");
    const searchInput = document.getElementById("stockSearch");

    if (
        suggestionsDiv &&
        !suggestionsDiv.contains(event.target) &&
        event.target !== searchInput
    ) {
        hideSuggestions();
    }
});