(() => {
  const NS = 'http://www.w3.org/2000/svg';

  function svgNode(name, attributes = {}, text = '') {
    const node = document.createElementNS(NS, name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text) node.textContent = text;
    return node;
  }

  function money(value, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
      style: 'currency', currency, maximumFractionDigits: 0,
    }).format(value);
  }

  function evidenceDate(value) {
    if (value instanceof Date) return value;
    const text = String(value ?? '');
    return new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(text) ? text : `${text}Z`);
  }

  function shortDate(value) {
    return new Intl.DateTimeFormat('en-GB', {
      day: '2-digit', month: 'short', year: '2-digit', timeZone: 'UTC',
    }).format(evidenceDate(value));
  }

  function metric(value, kind) {
    if (value == null || !Number.isFinite(Number(value))) return '—';
    if (kind === 'return_pct') return `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(2)}%`;
    if (kind === 'win_rate_pct' || kind === 'max_drawdown_pct') return `${Number(value).toFixed(2)}%`;
    if (kind === 'initial_balance' || kind === 'final_balance' || kind === 'net_profit') return money(Number(value));
    if (kind === 'trades' || kind === 'max_win_streak' || kind === 'max_loss_streak') {
      return Math.round(Number(value)).toLocaleString('en-US');
    }
    return Number(value).toFixed(2);
  }

  function signedValue(value, suffix = '', maximumFractionDigits = 2) {
    if (value == null || !Number.isFinite(Number(value))) return '—';
    const number = Number(value);
    const formatted = number.toLocaleString('en-US', { maximumFractionDigits });
    return `${number > 0 ? '+' : ''}${formatted}${suffix}`;
  }

  function hoverDate(value) {
    return new Intl.DateTimeFormat('en-GB', {
      day:'2-digit', month:'2-digit', year:'numeric',
      hour:'2-digit', minute:'2-digit', hour12:false, timeZone:'UTC',
    }).format(evidenceDate(value));
  }

  function nearestPoint(points, targetTime) {
    let low = 0;
    let high = points.length - 1;
    while (low < high) {
      const middle = Math.floor((low + high) / 2);
      if (points[middle].time.getTime() < targetTime) low = middle + 1;
      else high = middle;
    }
    if (low === 0) return points[0];
    const before = points[low - 1];
    const after = points[low];
    return Math.abs(before.time.getTime() - targetTime) <= Math.abs(after.time.getTime() - targetTime) ? before : after;
  }

  function addEquityHover(svg, datasets, geometry, currency) {
    const { width, height, left, right, top, bottom, firstTime, timeSpan, plotWidth, x, y } = geometry;
    const guide = svgNode('line', {
      x1:left, y1:top, x2:left, y2:height-bottom,
      stroke:'rgba(201,219,214,.55)', 'stroke-width':1, 'stroke-dasharray':'4 4', visibility:'hidden',
      'data-equity-hover-guide':'',
    });
    const markers = svgNode('g', { visibility:'hidden', 'pointer-events':'none', 'data-equity-hover-markers':'' });
    const tooltip = svgNode('g', { visibility:'hidden', 'pointer-events':'none', 'data-equity-hover-tooltip':'', role:'tooltip' });
    const tooltipWidth = 270;
    const tooltipHeight = 42 + datasets.length * 25;
    tooltip.appendChild(svgNode('rect', {
      width:tooltipWidth, height:tooltipHeight, rx:8,
      fill:'#111d22', stroke:'rgba(255,255,255,.18)', 'stroke-width':1,
    }));
    const dateLabel = svgNode('text', {
      x:13, y:19, fill:'#ffffff', 'font-size':12, 'font-weight':700,
      'font-family':'IBM Plex Mono, monospace',
    });
    tooltip.appendChild(dateLabel);
    const valueRows = datasets.map((dataset, index) => {
      const rowY = 42 + index * 25;
      tooltip.appendChild(svgNode('rect', { x:13, y:rowY-10, width:9, height:9, rx:2, fill:dataset.color }));
      const label = svgNode('text', {
        x:30, y:rowY-1, fill:'#c9dbd6', 'font-size':11,
        'font-family':'IBM Plex Mono, monospace',
      });
      tooltip.appendChild(label);
      return label;
    });
    const overlay = svgNode('rect', {
      x:left, y:top, width:plotWidth, height:height-top-bottom,
      fill:'transparent', 'pointer-events':'all', class:'equity-hover-overlay', tabindex:0,
      role:'button', 'aria-label':'Hover or tap the equity curve to inspect its date and balance',
    });
    let pinned = false;

    function showAt(clientX) {
      const bounds = svg.getBoundingClientRect();
      const scaledX = (clientX - bounds.left) * width / Math.max(bounds.width, 1);
      const cursorX = Math.max(left, Math.min(width-right, scaledX));
      const targetTime = firstTime + ((cursorX-left)/plotWidth)*timeSpan;
      const selected = datasets.map((dataset) => nearestPoint(dataset.series, targetTime));
      const primary = selected[0];
      const markerX = x(primary);
      guide.setAttribute('x1', markerX);
      guide.setAttribute('x2', markerX);
      guide.setAttribute('visibility', 'visible');
      markers.replaceChildren();
      selected.forEach((point, index) => {
        markers.appendChild(svgNode('circle', {
          cx:x(point), cy:y(point.balance), r:5, fill:datasets[index].color,
          stroke:'#07100f', 'stroke-width':3,
        }));
        valueRows[index].textContent = `${datasets[index].label}: ${money(point.balance, currency)}`;
      });
      markers.setAttribute('visibility', 'visible');
      dateLabel.textContent = `${hoverDate(primary.time)} UTC`;
      const tooltipX = markerX + tooltipWidth + 18 > width-right ? markerX-tooltipWidth-18 : markerX+18;
      const tooltipY = Math.max(top+4, Math.min(y(primary.balance)-28, height-bottom-tooltipHeight-4));
      tooltip.setAttribute('transform', `translate(${tooltipX},${tooltipY})`);
      tooltip.setAttribute('visibility', 'visible');
    }

    overlay.addEventListener('pointermove', (event) => { if (!pinned) showAt(event.clientX); });
    overlay.addEventListener('pointerleave', () => {
      if (pinned) return;
      guide.setAttribute('visibility', 'hidden');
      markers.setAttribute('visibility', 'hidden');
      tooltip.setAttribute('visibility', 'hidden');
    });
    overlay.addEventListener('pointerdown', (event) => {
      event.preventDefault();
      pinned = !pinned;
      showAt(event.clientX);
    });
    overlay.addEventListener('focus', () => {
      const bounds = svg.getBoundingClientRect();
      showAt(bounds.left + bounds.width * .72);
    });
    overlay.addEventListener('blur', () => {
      if (pinned) return;
      guide.setAttribute('visibility', 'hidden');
      markers.setAttribute('visibility', 'hidden');
      tooltip.setAttribute('visibility', 'hidden');
    });
    svg.appendChild(guide);
    svg.appendChild(markers);
    svg.appendChild(tooltip);
    svg.appendChild(overlay);
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
    }[character]));
  }

  function selectedEvidence(shell, payload) {
    if (!payload.datasets?.length) return payload;
    const wanted = shell.dataset.selectedDataset;
    return payload.datasets.find((dataset) => dataset.label === wanted) || payload.datasets[0];
  }

  const paginatedTradeTables = new WeakMap();

  function tradeRow(trade, supportsTradeCharts) {
    const row = document.createElement('tr');
    const resultClass = Number(trade.net_profit) >= 0 ? 'pnl-positive' : 'pnl-negative';
    let chartButton = '';
    if (trade.cache_slug && trade.cache_period && trade.number) {
      chartButton = `<button type="button" class="trade-chart-button" data-trade-chart-cache="${escapeHtml(trade.cache_slug)}" data-trade-chart-mode="${escapeHtml(trade.cache_mode || 'standard')}" data-trade-chart-period="${escapeHtml(trade.cache_period)}" data-trade-chart-number="${Number(trade.number)}">View trade</button>`;
    } else if (trade.verified_news_slug && trade.number) {
      chartButton = `<button type="button" class="trade-chart-button" data-trade-chart-verified-news="${escapeHtml(trade.verified_news_slug)}" data-trade-chart-number="${Number(trade.number)}">View trade</button>`;
    } else if (trade.job_id && trade.number) {
      chartButton = `<button type="button" class="trade-chart-button" data-trade-chart-job="${escapeHtml(trade.job_id)}" data-trade-chart-number="${Number(trade.number)}">View trade</button>`;
    }
    const chartAction = supportsTradeCharts
      ? `<td>${chartButton || '<span class="text-muted">Chart unavailable</span>'}</td>`
      : '';
    const rValue = signedValue(trade.estimated_r, 'R');
    const priceMove = trade.price_move == null
      ? '—'
      : `${signedValue(trade.price_move)} ${escapeHtml(trade.price_move_unit || 'points')}`;
    const commission = Number(trade.commission || 0);
    const swap = Number(trade.swap || 0);
    const costTitle = escapeHtml(trade.cost_basis || 'Native MT5 deal cost');
    row.innerHTML = `<td>${shortDate(trade.close_time)}</td><td class="table-ea">${escapeHtml(trade.ea)}</td><td>${escapeHtml(trade.result)}</td><td class="${resultClass}">${money(Number(trade.net_profit))}</td><td class="${commission < 0 ? 'pnl-negative' : ''}" title="${costTitle}">${money(commission)}</td><td class="${swap < 0 ? 'pnl-negative' : swap > 0 ? 'pnl-positive' : ''}" title="${costTitle}">${money(swap)}</td><td class="${resultClass}" title="Estimated from the configured equity-risk budget at entry">${rValue}</td><td class="${Number(trade.price_move) >= 0 ? 'pnl-positive' : 'pnl-negative'}">${priceMove}</td><td>${escapeHtml(trade.source)}</td>${chartAction}`;
    return row;
  }

  function renderTradePage(state) {
    const { body, pagination, supportsTradeCharts } = state;
    const total = state.trades.length;
    const totalPages = Math.max(1, Math.ceil(total / state.pageSize));
    state.page = Math.max(1, Math.min(state.page, totalPages));
    const start = (state.page - 1) * state.pageSize;
    const pageTrades = state.trades.slice(start, start + state.pageSize);
    body.replaceChildren();
    if (!pageTrades.length) {
      const row = document.createElement('tr');
      row.innerHTML = `<td colspan="${supportsTradeCharts ? 10 : 9}" class="empty-table">No closed trades in this selected period.</td>`;
      body.appendChild(row);
    } else {
      pageTrades.forEach((trade) => body.appendChild(tradeRow(trade, supportsTradeCharts)));
    }
    if (!pagination) return;
    const summary = pagination.querySelector('[data-trade-page-summary]');
    const previous = pagination.querySelector('[data-trade-page-prev]');
    const next = pagination.querySelector('[data-trade-page-next]');
    if (summary) {
      const firstRow = total ? start + 1 : 0;
      const lastRow = Math.min(start + state.pageSize, total);
      summary.textContent = total
        ? `Showing ${firstRow}–${lastRow} of ${total.toLocaleString('en-US')} trades · Page ${state.page} of ${totalPages}`
        : 'No trades in this period';
    }
    if (previous) previous.disabled = state.page <= 1;
    if (next) next.disabled = state.page >= totalPages;
  }

  function renderTradeTable(root, body, trades, supportsTradeCharts, payloadKey) {
    const pagination = root.querySelector('[data-trade-pagination]');
    if (!pagination) {
      const state = { body, pagination:null, supportsTradeCharts, trades:[...trades].reverse(), page:1, pageSize:Math.max(trades.length, 1) };
      renderTradePage(state);
      return;
    }
    let state = paginatedTradeTables.get(pagination);
    if (!state) {
      const sizeInput = pagination.querySelector('[data-trade-page-size]');
      state = {
        body, pagination, supportsTradeCharts, trades:[], page:1,
        pageSize:Number(sizeInput?.value) || 10, payloadKey:'',
      };
      pagination.querySelector('[data-trade-page-prev]')?.addEventListener('click', () => {
        state.page -= 1;
        renderTradePage(state);
      });
      pagination.querySelector('[data-trade-page-next]')?.addEventListener('click', () => {
        state.page += 1;
        renderTradePage(state);
      });
      sizeInput?.addEventListener('change', () => {
        state.pageSize = Number(sizeInput.value) || 10;
        state.page = 1;
        renderTradePage(state);
      });
      paginatedTradeTables.set(pagination, state);
    }
    state.body = body;
    state.supportsTradeCharts = supportsTradeCharts;
    state.trades = [...trades].reverse();
    if (state.payloadKey !== payloadKey) state.page = 1;
    state.payloadKey = payloadKey;
    renderTradePage(state);
  }

  function renderPeriodEvidence(shell, payload) {
    const root = shell.closest('[data-evidence-scope]') || shell.closest('section') || document;
    const selected = selectedEvidence(shell, payload);
    const stats = selected.stats || payload.stats;
    root.querySelectorAll('[data-dynamic-stat]').forEach((node) => {
      const key = node.dataset.dynamicStat;
      node.textContent = metric(stats?.[key], key);
      if (key === 'return_pct' && stats?.[key] != null) {
        node.classList.toggle('text-mint', Number(stats[key]) >= 0);
        node.classList.toggle('text-red-300', Number(stats[key]) < 0);
      }
    });
    root.querySelectorAll('[data-dynamic-period]').forEach((node) => {
      node.textContent = payload.period || `${stats?.from || ''} to ${stats?.to || ''}`;
    });
    root.querySelectorAll('[data-dynamic-source]').forEach((node) => {
      node.textContent = payload.notice || 'Precomputed native MT5 evidence.';
    });
    root.querySelectorAll('[data-dynamic-history-quality]').forEach((node) => {
      node.textContent = payload.history_quality || stats?.history_quality || 'Not reported';
    });
    const evidenceTitle = root.querySelector('[data-dynamic-evidence-title]');
    const periodInput = root.querySelector('[data-chart-period]');
    if (evidenceTitle && periodInput) {
      const periodLabel = periodInput.options[periodInput.selectedIndex]?.textContent || payload.period_key;
      evidenceTitle.textContent = `Precomputed ${periodLabel} — active recommended configuration`;
    }
    const body = root.querySelector('[data-backtest-trades-body]');
    if (body) {
      const trades = selected.trades || payload.trades || [];
      const supportsTradeCharts = Boolean(root.querySelector('[data-trade-chart-panel]'));
      const payloadKey = `${payload.period_key || payload.period || ''}|${selected.label || ''}|${trades.length}`;
      renderTradeTable(root, body, trades, supportsTradeCharts, payloadKey);
    }
    const note = root.querySelector('[data-range-note]');
    if (note && stats) {
      const extras = [
        stats.sharpe_ratio == null ? null : `Sharpe ${Number(stats.sharpe_ratio).toFixed(2)}`,
        stats.recovery_factor == null ? null : `Recovery ${Number(stats.recovery_factor).toFixed(2)}`,
      ].filter(Boolean).join(' · ');
      const tradeSource = ['precomputed-native-mt5-cache', 'native-mt5-background-job', 'adaptive-replay-of-native-mt5-cache', 'verified-news-schedule-replay'].includes(payload.source)
        ? 'Trade rows are parsed directly from native MT5 deals.'
        : 'Trade rows are reconstructed from archived MT5 balance events.';
      const displayLimit = Number(payload.cached_trade_count) > Number(payload.displayed_trade_count)
        ? ` Showing the latest ${Number(payload.displayed_trade_count).toLocaleString('en-US')} of ${Number(payload.cached_trade_count).toLocaleString('en-US')} cached trades.`
        : '';
      const coverage = payload.trade_coverage_from && payload.trade_coverage_to
        ? ` Closed-trade coverage: ${shortDate(payload.trade_coverage_from)} to ${shortDate(payload.trade_coverage_to)}.`
        : ' No closed trades were recorded in this period.';
      const solvencyWarning = Number(stats.max_drawdown_pct) >= 100
        ? ' CRITICAL: this combined-risk overlay crossed below zero; it was not survivable at the tested summed sizing.'
        : '';
      note.textContent = `${stats.from} to ${stats.to}${extras ? ` · ${extras}` : ''}. ${tradeSource}${coverage}${displayLimit}${solvencyWarning}`;
    }
  }

  const ANALYSIS_COLOURS = ['#7ef7c7', '#68a7ff', '#f8d889', '#c8b5ff', '#fca5a5', '#8eeeff'];

  function prepareAnalysisSvg(svg, title) {
    svg.replaceChildren();
    svg.appendChild(svgNode('title', {}, title));
  }

  function analysisText(svg, x, y, text, attributes = {}) {
    svg.appendChild(svgNode('text', {
      x, y, fill: '#91aaa4', 'font-size': 11,
      'font-family': 'IBM Plex Mono, monospace', ...attributes,
    }, text));
  }

  function drawDrawdown(svg, points) {
    prepareAnalysisSvg(svg, 'Portfolio drawdown as a percentage below the prior balance peak');
    const values = (points || []).map((point) => ({
      time: evidenceDate(point.time), value: Number(point.drawdown_pct),
    })).filter((point) => Number.isFinite(point.time.getTime()) && Number.isFinite(point.value));
    if (values.length < 2) return;
    const width = 1000, height = 260, left = 68, right = 20, top = 14, bottom = 38;
    const plotWidth = width - left - right, plotHeight = height - top - bottom;
    const minimum = Math.min(-0.1, ...values.map((point) => point.value));
    const first = values[0].time.getTime(), last = values.at(-1).time.getTime();
    const x = (point) => left + ((point.time.getTime() - first) / Math.max(last - first, 1)) * plotWidth;
    const y = (value) => top + ((0 - value) / (0 - minimum)) * plotHeight;
    for (let index = 0; index < 5; index += 1) {
      const value = minimum * index / 4;
      const yy = y(value);
      svg.appendChild(svgNode('line', { x1:left, y1:yy, x2:width-right, y2:yy, stroke:'rgba(255,255,255,.075)', 'stroke-width':1 }));
      analysisText(svg, left - 10, yy + 4, `${value.toFixed(1)}%`, { 'text-anchor':'end' });
    }
    const line = values.map((point) => `${x(point).toFixed(2)},${y(point.value).toFixed(2)}`).join(' ');
    svg.appendChild(svgNode('polygon', { points:`${left},${y(0)} ${line} ${width-right},${y(0)}`, fill:'rgba(248,113,113,.16)' }));
    svg.appendChild(svgNode('polyline', { points:line, fill:'none', stroke:'#f87171', 'stroke-width':2.2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }));
    analysisText(svg, left, height - 10, shortDate(values[0].time));
    analysisText(svg, width - right, height - 10, shortDate(values.at(-1).time), { 'text-anchor':'end' });
  }

  function drawHorizontalBars(svg, rows, valueKey, valueFormatter, title, colour = '#7ef7c7') {
    prepareAnalysisSvg(svg, title);
    const values = (rows || []).map((row) => ({ label:row.symbol, value:Number(row[valueKey]) }))
      .filter((row) => row.label && Number.isFinite(row.value)).slice(0, 7);
    if (!values.length) return;
    const width = 560, height = 300, left = 92, right = 65, top = 16, bottom = 30;
    const plotWidth = width-left-right, rowHeight = (height-top-bottom)/values.length;
    const minimum = Math.min(0, ...values.map((row) => row.value));
    const maximum = Math.max(0, ...values.map((row) => row.value));
    const span = Math.max(maximum - minimum, 1);
    const x = (value) => left + (value-minimum)/span*plotWidth;
    const zero = x(0);
    svg.appendChild(svgNode('line', { x1:zero, y1:top, x2:zero, y2:height-bottom, stroke:'rgba(255,255,255,.18)', 'stroke-width':1 }));
    values.forEach((row, index) => {
      const yy = top + index*rowHeight + rowHeight*.19;
      const end = x(row.value);
      const rect = svgNode('rect', { x:Math.min(zero,end), y:yy, width:Math.max(Math.abs(end-zero),1), height:rowHeight*.62, rx:3, fill:row.value >= 0 ? colour : '#f87171', opacity:.8 });
      rect.appendChild(svgNode('title', {}, `${row.label}: ${valueFormatter(row.value)}`));
      svg.appendChild(rect);
      analysisText(svg, left-10, yy+rowHeight*.4, row.label, { 'text-anchor':'end' });
      const positiveCrowded = row.value >= 0 && end > width-right-56;
      const negativeCrowded = row.value < 0 && end < left+56;
      const labelX = row.value >= 0 ? (positiveCrowded ? end-6 : Math.min(end+7,width-3)) : (negativeCrowded ? end+6 : Math.max(end-7,3));
      const labelAnchor = row.value >= 0 ? (positiveCrowded ? 'end' : 'start') : (negativeCrowded ? 'start' : 'end');
      analysisText(svg, labelX, yy+rowHeight*.4, valueFormatter(row.value), { 'text-anchor':labelAnchor, fill:row.value >= 0 ? '#baffdf' : '#fca5a5' });
    });
  }

  function drawMonthlyPnl(svg, rows) {
    prepareAnalysisSvg(svg, 'Monthly realized profit and loss');
    const values = (rows || []).map((row) => ({ month:String(row.month), value:Number(row.net_profit) })).filter((row) => Number.isFinite(row.value));
    if (!values.length) return;
    const width=560, height=300, left=56, right=15, top=18, bottom=48;
    const plotWidth=width-left-right, plotHeight=height-top-bottom;
    const minimum=Math.min(0,...values.map((row)=>row.value)), maximum=Math.max(0,...values.map((row)=>row.value));
    const span=Math.max(maximum-minimum,1), y=(value)=>top+(maximum-value)/span*plotHeight, zero=y(0);
    for(let index=0;index<5;index+=1){const value=maximum-index/4*span;const yy=y(value);svg.appendChild(svgNode('line',{x1:left,y1:yy,x2:width-right,y2:yy,stroke:'rgba(255,255,255,.065)','stroke-width':1}));analysisText(svg,left-7,yy+4,money(value),{'text-anchor':'end'});}
    const slot=plotWidth/values.length, barWidth=Math.max(2,slot*.68), labelStep=Math.max(1,Math.ceil(values.length/6));
    values.forEach((row,index)=>{const xx=left+index*slot+(slot-barWidth)/2;const yy=y(row.value);const rect=svgNode('rect',{x:xx,y:Math.min(yy,zero),width:barWidth,height:Math.max(Math.abs(zero-yy),1),rx:1.5,fill:row.value>=0?'#7ef7c7':'#f87171',opacity:.78});rect.appendChild(svgNode('title',{},`${row.month}: ${money(row.value)}`));svg.appendChild(rect);if(index%labelStep===0||index===values.length-1){analysisText(svg,xx+barWidth/2,height-18,row.month.slice(2),{'text-anchor':'middle'});}});
  }

  function allocationArc(cx, cy, radius, start, end) {
    const point = (angle) => [cx + radius*Math.cos(angle), cy + radius*Math.sin(angle)];
    const [x1,y1]=point(start), [x2,y2]=point(end);
    return `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${end-start>Math.PI?1:0} 1 ${x2} ${y2} Z`;
  }

  function drawAllocation(svg, assets, legend) {
    prepareAnalysisSvg(svg, 'Share of executed portfolio trades by asset');
    legend.replaceChildren();
    const rows=(assets||[]).filter((row)=>Number(row.trades)>0);
    const total=rows.reduce((sum,row)=>sum+Number(row.trades),0);
    let angle=-Math.PI/2;
    rows.forEach((row,index)=>{const share=Number(row.trades)/Math.max(total,1);const next=angle+share*Math.PI*2;const colour=ANALYSIS_COLOURS[index%ANALYSIS_COLOURS.length];const path=svgNode('path',{d:allocationArc(150,150,112,angle,next),fill:colour,stroke:'#0a1513','stroke-width':2});path.appendChild(svgNode('title',{},`${row.symbol}: ${row.trades} trades (${(share*100).toFixed(1)}%)`));svg.appendChild(path);const item=document.createElement('div');item.className='allocation-legend-row';item.innerHTML=`<i style="background:${colour}"></i><span>${escapeHtml(row.symbol)}</span><strong>${Number(row.trades).toLocaleString('en-US')} · ${(share*100).toFixed(1)}%</strong>`;legend.appendChild(item);angle=next;});
    svg.appendChild(svgNode('circle',{cx:150,cy:150,r:61,fill:'#0a1513'}));
    analysisText(svg,150,146,total.toLocaleString('en-US'),{'text-anchor':'middle',fill:'#edf8f4','font-size':24,'font-weight':700});
    analysisText(svg,150,169,'TRADES',{'text-anchor':'middle','font-size':10});
  }

  function renderPortfolioAnalytics(root, payload) {
    const container=root.querySelector('[data-portfolio-analytics]');
    const analytics=payload.analytics;
    if(!container||!analytics)return;
    const tradeStats=analytics.trade_stats||{};
    const stats=payload.stats||{};
    const statValues={net_profit:stats.net_profit,...tradeStats};
    container.querySelectorAll('[data-analytics-stat]').forEach((node)=>{const key=node.dataset.analyticsStat;node.textContent=key==='payoff_ratio'?metric(statValues[key],key):money(Number(statValues[key]));const negative=Number(statValues[key])<0;node.classList.toggle('pnl-negative',negative);node.classList.toggle('pnl-positive',!negative&&key!=='payoff_ratio');});
    const periodLabel=container.querySelector('[data-analytics-period]');if(periodLabel)periodLabel.textContent=payload.period||payload.period_key;
    drawDrawdown(container.querySelector('[data-analysis-chart="drawdown"]'),analytics.drawdown_series);
    drawHorizontalBars(container.querySelector('[data-analysis-chart="asset-return"]'),analytics.assets,'return_contribution_pct',(value)=>signedValue(value,'%'),'Return contribution by asset');
    drawMonthlyPnl(container.querySelector('[data-analysis-chart="monthly-pnl"]'),analytics.monthly_pnl);
    drawHorizontalBars(container.querySelector('[data-analysis-chart="asset-win-rate"]'),analytics.assets,'win_rate_pct',(value)=>`${value.toFixed(1)}%`,'Win rate by asset','#68a7ff');
    const directionGrid=container.querySelector('[data-direction-grid]');directionGrid.replaceChildren();
    (analytics.directions||[]).forEach((row)=>{const card=document.createElement('div');const isLong=row.side==='Long';card.className=`direction-card ${isLong?'long':'short'}`;card.innerHTML=`<div class="direction-card-header"><strong>${isLong?'↗ Bullish (LONG)':'↘ Bearish (SHORT)'}</strong><span>${Number(row.trades).toLocaleString('en-US')} trades · ${Number(row.trade_share_pct).toFixed(1)}%</span></div><div class="direction-metrics"><div><span>Win rate</span><strong>${Number(row.win_rate_pct||0).toFixed(2)}%</strong></div><div><span>Wins</span><strong>${Number(row.wins).toLocaleString('en-US')}</strong></div><div><span>Average P/L</span><strong class="${Number(row.avg_pnl)>=0?'pnl-positive':'pnl-negative'}">${money(Number(row.avg_pnl||0))}</strong></div></div>`;directionGrid.appendChild(card);const share=container.querySelector(isLong?'[data-direction-long-share]':'[data-direction-short-share]');if(share)share.style.width=`${Number(row.trade_share_pct||0)}%`;});
    const assetBody=container.querySelector('[data-asset-breakdown-body]');assetBody.replaceChildren();(analytics.assets||[]).forEach((row)=>{const tr=document.createElement('tr');tr.innerHTML=`<td>${escapeHtml(row.symbol)}</td><td class="${Number(row.return_contribution_pct)>=0?'pnl-positive':'pnl-negative'}">${signedValue(row.return_contribution_pct,'%')}</td><td>${Number(row.win_rate_pct||0).toFixed(2)}%</td><td>${Number(row.trades).toLocaleString('en-US')}</td><td class="${Number(row.net_profit)>=0?'pnl-positive':'pnl-negative'}">${money(Number(row.net_profit))}</td>`;assetBody.appendChild(tr);});
    drawAllocation(container.querySelector('[data-analysis-chart="allocation"]'),analytics.assets,container.querySelector('[data-allocation-legend]'));
    const eaBody=container.querySelector('[data-ea-breakdown-body]');eaBody.replaceChildren();(payload.included_eas||[]).forEach((row)=>{const tr=document.createElement('tr');const recommended=row.recommended||row;tr.innerHTML=`<td>${escapeHtml(row.label)}</td><td>${escapeHtml(row.symbol)}</td><td class="${Number(recommended.return_pct)>=0?'pnl-positive':'pnl-negative'}">${signedValue(recommended.return_pct,'%')}</td><td>${metric(recommended.profit_factor,'profit_factor')}</td><td>${metric(recommended.win_rate_pct,'win_rate_pct')}</td><td>${metric(recommended.max_drawdown_pct,'max_drawdown_pct')}</td><td>${metric(recommended.trades,'trades')}</td><td>${Number(row.skipped_trades||0).toLocaleString('en-US')}</td>`;eaBody.appendChild(tr);});
  }

  function drawTradeChart(panel, payload) {
    const svg = panel.querySelector('[data-trade-chart-svg]');
    const status = panel.querySelector('[data-trade-chart-status]');
    const bars = (payload.bars || []).map((bar) => ({
      ...bar,
      time: evidenceDate(bar.time),
      open: Number(bar.open), high: Number(bar.high), low: Number(bar.low), close: Number(bar.close),
    })).filter((bar) => Number.isFinite(bar.time.getTime()) && [bar.open, bar.high, bar.low, bar.close].every(Number.isFinite));
    if (bars.length < 2) throw new Error('MT5 returned too few candles for this trade.');
    const trade = payload.trade;
    const width = 1000, height = 430, left = 82, right = 34, top = 30, bottom = 58;
    const plotWidth = width - left - right, plotHeight = height - top - bottom;
    const prices = bars.flatMap((bar) => [bar.high, bar.low]);
    prices.push(Number(trade.open_price), Number(trade.close_price));
    let minimum = Math.min(...prices), maximum = Math.max(...prices);
    const padding = Math.max((maximum - minimum) * .1, Math.abs(maximum) * .0002, .00001);
    minimum -= padding; maximum += padding;
    const x = (index) => left + ((index + .5) / bars.length) * plotWidth;
    const y = (price) => top + ((maximum - price) / Math.max(maximum - minimum, .000001)) * plotHeight;
    const candleWidth = Math.max(1.2, Math.min(9, plotWidth / bars.length * .68));
    svg.replaceChildren();
    for (let index = 0; index < 5; index += 1) {
      const yy = top + index / 4 * plotHeight;
      const price = maximum - index / 4 * (maximum - minimum);
      svg.appendChild(svgNode('line', { x1:left, y1:yy, x2:width-right, y2:yy, stroke:'rgba(255,255,255,.08)', 'stroke-width':1 }));
      svg.appendChild(svgNode('text', { x:left-10, y:yy+4, fill:'#789089', 'font-size':11, 'font-family':'IBM Plex Mono, monospace', 'text-anchor':'end' }, price.toLocaleString('en-US', { maximumFractionDigits: 5 })));
    }
    bars.forEach((bar, index) => {
      const colour = bar.close >= bar.open ? '#7ef7c7' : '#f87171';
      svg.appendChild(svgNode('line', { x1:x(index), y1:y(bar.high), x2:x(index), y2:y(bar.low), stroke:colour, 'stroke-width':1 }));
      const bodyTop = Math.min(y(bar.open), y(bar.close));
      const bodyHeight = Math.max(1.25, Math.abs(y(bar.open) - y(bar.close)));
      svg.appendChild(svgNode('rect', { x:x(index)-candleWidth/2, y:bodyTop, width:candleWidth, height:bodyHeight, rx:.7, fill:colour }));
    });
    const firstTime = bars[0].time.getTime(), lastTime = bars.at(-1).time.getTime();
    const nearestX = (value) => {
      const target = evidenceDate(value).getTime();
      if (!Number.isFinite(target) || lastTime === firstTime) return left;
      return left + Math.max(0, Math.min(1, (target - firstTime) / (lastTime - firstTime))) * plotWidth;
    };
    const rValue = signedValue(trade.estimated_r, 'R');
    const priceMove = trade.price_move == null ? 'movement unavailable' : `${signedValue(trade.price_move)} ${trade.price_move_unit || 'points'}`;
    const markers = [
      { label:`ENTRY ${trade.side}`, time:trade.open_time, price:Number(trade.open_price), colour:'#68a7ff' },
      { label:`EXIT ${trade.result} · ${rValue} · ${priceMove}`, time:trade.close_time, price:Number(trade.close_price), colour:Number(trade.net_profit) >= 0 ? '#7ef7c7' : '#f87171' },
    ];
    markers.forEach((marker, index) => {
      const xx = nearestX(marker.time), yy = y(marker.price);
      const anchorAtEnd = xx > width - right - 300;
      svg.appendChild(svgNode('line', { x1:left, y1:yy, x2:width-right, y2:yy, stroke:marker.colour, 'stroke-width':1.4, 'stroke-dasharray':'6 5', opacity:.8 }));
      svg.appendChild(svgNode('circle', { cx:xx, cy:yy, r:6, fill:marker.colour, stroke:'#07100f', 'stroke-width':3 }));
      svg.appendChild(svgNode('text', { x:xx+(anchorAtEnd?-10:10), y:yy+(index ? 18 : -10), fill:marker.colour, 'font-size':11, 'font-weight':700, 'font-family':'IBM Plex Mono, monospace', 'text-anchor':anchorAtEnd?'end':'start' }, `${marker.label} · ${marker.price}`));
    });
    svg.appendChild(svgNode('text', { x:left, y:height-18, fill:'#789089', 'font-size':11, 'font-family':'IBM Plex Mono, monospace' }, bars[0].time.toLocaleString('en-GB')));
    svg.appendChild(svgNode('text', { x:width-right, y:height-18, fill:'#789089', 'font-size':11, 'font-family':'IBM Plex Mono, monospace', 'text-anchor':'end' }, bars.at(-1).time.toLocaleString('en-GB')));
    panel.querySelector('[data-trade-chart-title]').textContent = `${payload.symbol} ${payload.timeframe} · ${trade.side} trade`;
    panel.querySelector('[data-trade-chart-meta]').textContent = `${shortDate(trade.close_time)} · ${trade.volume} lots · ${money(Number(trade.net_profit))} net · ${money(Number(trade.commission || 0))} commission · ${money(Number(trade.swap || 0))} swap · ${rValue} estimated · ${priceMove} · broker MT5 candles`;
    status.classList.add('hidden');
    svg.classList.remove('hidden');
  }

  async function openTradeChart(button) {
    const root = button.closest('section') || document;
    const panel = root.querySelector('[data-trade-chart-panel]');
    const status = panel?.querySelector('[data-trade-chart-status]');
    const svg = panel?.querySelector('[data-trade-chart-svg]');
    if (!panel || !status || !svg) return;
    panel.classList.remove('hidden');
    status.classList.remove('hidden');
    status.textContent = 'Loading broker candles from MT5…';
    svg.classList.add('hidden');
    panel.scrollIntoView({ behavior:'smooth', block:'nearest' });
    try {
      const url = button.dataset.tradeChartCache
        ? `/api/evidence/${encodeURIComponent(button.dataset.tradeChartCache)}/cached-trades/${encodeURIComponent(button.dataset.tradeChartPeriod)}/${encodeURIComponent(button.dataset.tradeChartNumber)}/chart?mode=${encodeURIComponent(button.dataset.tradeChartMode || 'standard')}`
        : button.dataset.tradeChartVerifiedNews
          ? `/api/evidence/${encodeURIComponent(button.dataset.tradeChartVerifiedNews)}/verified-trades/${encodeURIComponent(button.dataset.tradeChartNumber)}/chart`
          : `/api/evidence/jobs/${encodeURIComponent(button.dataset.tradeChartJob)}/trades/${encodeURIComponent(button.dataset.tradeChartNumber)}/chart`;
      const response = await fetch(url, { cache:'no-store' });
      if (!response.ok) throw new Error(await responseMessage(response));
      drawTradeChart(panel, await response.json());
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : 'Trade chart could not be loaded.';
    }
  }

  function drawChart(shell, payload) {
    const svg = shell.querySelector('[data-chart-svg]');
    const status = shell.querySelector('[data-chart-status]');
    const rawDatasets = payload.datasets?.length
      ? payload.datasets
      : [{ label: payload.label || 'Equity', color: '#7ef7c7', series: payload.series || [] }];
    const datasets = rawDatasets.map((dataset, index) => ({
      label: dataset.label || `Series ${index + 1}`,
      color: dataset.color || (index ? '#68a7ff' : '#7ef7c7'),
      series: (dataset.series || [])
        .map((point) => ({ time: evidenceDate(point.time), balance: Number(point.balance) }))
        .filter((point) => Number.isFinite(point.time.getTime()) && Number.isFinite(point.balance))
        .sort((first, second) => first.time - second.time),
    })).filter((dataset) => dataset.series.length >= 2);
    if (!datasets.length) throw new Error('Not enough balance points to draw this curve.');
    const allPoints = datasets.flatMap((dataset) => dataset.series);

    status.classList.add('hidden');
    svg.classList.remove('hidden');
    svg.replaceChildren();

    const width = 1000, height = 360, left = 78, right = 28, top = 28, bottom = 48;
    const balances = allPoints.map((point) => point.balance);
    let minimum = Math.min(...balances), maximum = Math.max(...balances);
    const padding = Math.max((maximum - minimum) * 0.12, Math.abs(maximum) * 0.01, 1);
    minimum -= padding;
    maximum += padding;
    const firstTime = Math.min(...allPoints.map((point) => point.time.getTime()));
    const lastTime = Math.max(...allPoints.map((point) => point.time.getTime()));
    const timeSpan = Math.max(lastTime - firstTime, 1);
    const plotWidth = width - left - right;
    const plotHeight = height - top - bottom;
    const x = (point) => left + ((point.time.getTime() - firstTime) / timeSpan) * plotWidth;
    const y = (value) => top + ((maximum - value) / (maximum - minimum)) * plotHeight;

    const defs = svgNode('defs');
    const gradientId = `equity-fill-${Math.random().toString(36).slice(2)}`;
    const gradient = svgNode('linearGradient', { id: gradientId, x1: 0, y1: 0, x2: 0, y2: 1 });
    gradient.appendChild(svgNode('stop', { offset: '0%', 'stop-color': '#7ef7c7', 'stop-opacity': .22 }));
    gradient.appendChild(svgNode('stop', { offset: '100%', 'stop-color': '#7ef7c7', 'stop-opacity': 0 }));
    defs.appendChild(gradient);
    svg.appendChild(defs);

    for (let index = 0; index < 5; index += 1) {
      const yy = top + (index / 4) * plotHeight;
      const value = maximum - (index / 4) * (maximum - minimum);
      svg.appendChild(svgNode('line', {
        x1: left, y1: yy, x2: width - right, y2: yy,
        stroke: 'rgba(255,255,255,.09)', 'stroke-width': 1,
      }));
      svg.appendChild(svgNode('text', {
        x: left - 12, y: yy + 4, fill: '#789089', 'font-size': 11,
        'font-family': 'IBM Plex Mono, monospace', 'text-anchor': 'end',
      }, money(value, payload.currency || 'USD')));
    }

    datasets.forEach((dataset, index) => {
      const linePoints = dataset.series.map((point) => `${x(point).toFixed(2)},${y(point.balance).toFixed(2)}`).join(' ');
      if (datasets.length === 1) {
        const areaPoints = `${left},${top + plotHeight} ${linePoints} ${width - right},${top + plotHeight}`;
        svg.appendChild(svgNode('polygon', { points: areaPoints, fill: `url(#${gradientId})` }));
      }
      svg.appendChild(svgNode('polyline', {
        points: linePoints, fill: 'none', stroke: dataset.color,
        'stroke-width': index ? 2.5 : 3, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
      }));
      const finalPoint = dataset.series.at(-1);
      svg.appendChild(svgNode('circle', {
        cx: x(finalPoint), cy: y(finalPoint.balance), r: 5, fill: dataset.color,
        stroke: '#07100f', 'stroke-width': 3,
      }));
      const legendX = left + index * 180;
      svg.appendChild(svgNode('line', { x1: legendX, y1: 14, x2: legendX + 22, y2: 14, stroke: dataset.color, 'stroke-width': 4 }));
      svg.appendChild(svgNode('text', { x: legendX + 30, y: 18, fill: '#c9dbd6', 'font-size': 11, 'font-family': 'IBM Plex Mono, monospace' }, dataset.label));
    });
    const firstPoint = allPoints.reduce((earliest, point) => point.time < earliest.time ? point : earliest, allPoints[0]);
    const finalPoint = datasets[0].series.at(-1);
    svg.appendChild(svgNode('text', {
      x: left, y: height - 14, fill: '#789089', 'font-size': 11,
      'font-family': 'IBM Plex Mono, monospace',
    }, shortDate(firstPoint.time)));
    svg.appendChild(svgNode('text', {
      x: width - right, y: height - 14, fill: '#789089', 'font-size': 11,
      'font-family': 'IBM Plex Mono, monospace', 'text-anchor': 'end',
    }, shortDate(finalPoint.time)));
    svg.appendChild(svgNode('text', {
      x: width - right - 12, y: Math.max(y(finalPoint.balance) - 12, top + 12),
      fill: '#baffdf', 'font-size': 12, 'font-weight': 700,
      'font-family': 'IBM Plex Mono, monospace', 'text-anchor': 'end',
    }, money(finalPoint.balance, payload.currency || 'USD')));
    if (payload.notice) {
      svg.appendChild(svgNode('text', {
        x: left, y: height - 30, fill: '#d4b968', 'font-size': 10,
        'font-family': 'IBM Plex Mono, monospace',
      }, payload.notice));
      shell.title = payload.notice;
    }
    addEquityHover(svg, datasets, {
      width, height, left, right, top, bottom, firstTime, timeSpan, plotWidth, x, y,
    }, payload.currency || 'USD');
  }

  async function loadChart(shell) {
    const status = shell.querySelector('[data-chart-status]');
    const root = shell.closest('[data-evidence-scope]') || shell.closest('section') || document;
    const applyButton = root.querySelector('[data-chart-apply]');
    const progress = root.querySelector('[data-evidence-progress]');
    const progressText = root.querySelector('[data-evidence-progress-text]');
    const previousButtonText = applyButton?.textContent || 'Update evidence';
    if (applyButton) {
      applyButton.disabled = true;
      applyButton.setAttribute('aria-busy', 'true');
      applyButton.textContent = 'Updating…';
    }
    if (progress) {
      progress.classList.remove('hidden', 'is-complete', 'is-error');
      if (progressText) progressText.textContent = 'Loading archived MT5 evidence…';
    }
    try {
      const periodInput = root.querySelector('[data-chart-period]');
      const url = new URL(shell.dataset.seriesUrl, window.location.origin);
      url.searchParams.set('period', periodInput?.value || '3y');
      status.classList.remove('hidden');
      status.textContent = 'Loading precomputed evidence…';
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) throw new Error(`The curve endpoint returned ${response.status}.`);
      const payload = await response.json();
      drawChart(shell, payload);
      renderPeriodEvidence(shell, payload);
      renderPortfolioAnalytics(root, payload);
      if (periodInput && window.location.pathname.startsWith('/eas/')) {
        const pageUrl = new URL(window.location.href);
        pageUrl.searchParams.set('period', payload.period_key);
        window.history.replaceState(null, '', pageUrl);
        root.querySelectorAll('a[href*="?mode="]').forEach((link) => {
          const modeUrl = new URL(link.href);
          modeUrl.searchParams.set('period', payload.period_key);
          link.href = modeUrl.toString();
        });
      }
      if (progress) {
        progress.classList.add('is-complete');
        if (progressText) progressText.textContent = `Cached native MT5 evidence loaded through ${payload.available_to}.`;
      }
    } catch (error) {
      status.classList.remove('hidden');
      status.textContent = 'Equity curve is temporarily unavailable.';
      status.title = String(error);
      if (progress) {
        progress.classList.add('is-error');
        if (progressText) progressText.textContent = error instanceof Error ? error.message : 'Evidence update failed.';
      }
    } finally {
      if (applyButton) {
        applyButton.disabled = false;
        applyButton.removeAttribute('aria-busy');
        applyButton.textContent = previousButtonText;
      }
    }
  }

  async function responseMessage(response) {
    try {
      const payload = await response.json();
      return payload.detail || payload.error || `Request failed with status ${response.status}.`;
    } catch (_error) {
      return `Request failed with status ${response.status}.`;
    }
  }

  document.querySelectorAll('[data-equity-graph]').forEach((shell) => {
    const root = shell.closest('section') || document;
    root.querySelector('[data-chart-apply]')?.addEventListener('click', () => loadChart(shell));
    root.querySelector('[data-chart-period]')?.addEventListener('change', () => loadChart(shell));
    loadChart(shell);
  });
  document.addEventListener('click', (event) => {
    const tradeButton = event.target.closest('[data-trade-chart-job],[data-trade-chart-cache],[data-trade-chart-verified-news]');
    if (tradeButton) openTradeChart(tradeButton);
    const closeButton = event.target.closest('[data-trade-chart-close]');
    if (closeButton) closeButton.closest('[data-trade-chart-panel]')?.classList.add('hidden');
  });
})();
