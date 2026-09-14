(() => {
  const byId = (id) => document.getElementById(id);
  const state = { data: null, trades: [], currency: 'USD' };
  const money = (value) => new Intl.NumberFormat(undefined, { style: 'currency', currency: state.currency, maximumFractionDigits: 2 }).format(Number(value || 0));
  const number = (value, digits = 2) => Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const price = (value) => value == null ? '—' : Number(value).toLocaleString(undefined, { maximumFractionDigits: 5 });
  const dateTime = (value) => value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—';
  const duration = (seconds) => {
    const value = Number(seconds || 0);
    if (value < 60) return `${value}s`;
    if (value < 3600) return `${Math.floor(value / 60)}m`;
    if (value < 86400) return `${Math.floor(value / 3600)}h ${Math.floor((value % 3600) / 60)}m`;
    return `${Math.floor(value / 86400)}d ${Math.floor((value % 86400) / 3600)}h`;
  };
  const setText = (id, value) => { const node = byId(id); if (node) node.textContent = value; };
  const pnlClass = (value) => Number(value) >= 0 ? 'pnl-positive' : 'pnl-negative';
  const setMoney = (id, value) => {
    const node = byId(id);
    if (!node) return;
    node.textContent = money(value);
    node.classList.remove('pnl-positive', 'pnl-negative');
    if (Number(value) !== 0) node.classList.add(pnlClass(value));
  };
  const cell = (row, value, className = '') => {
    const node = document.createElement('td');
    node.textContent = value;
    if (className) node.className = className;
    row.appendChild(node);
    return node;
  };
  const emptyRow = (body, colspan, message) => {
    body.replaceChildren();
    const row = document.createElement('tr');
    const node = cell(row, message, 'empty-table');
    node.colSpan = colspan;
    body.appendChild(row);
  };

  function renderPositions(positions) {
    const body = byId('positions-body');
    setText('positions-badge', `${positions.length} active`);
    setText('stat-open-count', `${positions.length} open position${positions.length === 1 ? '' : 's'}`);
    if (!positions.length) return emptyRow(body, 9, 'No open positions right now.');
    body.replaceChildren();
    positions.forEach((item) => {
      const row = document.createElement('tr');
      cell(row, item.ea, 'table-ea');
      cell(row, item.symbol, 'font-mono');
      cell(row, item.side, item.side === 'Buy' ? 'side-buy' : 'side-sell');
      cell(row, number(item.volume, 2));
      cell(row, price(item.open_price));
      cell(row, price(item.current_price));
      cell(row, `${price(item.stop_loss)} / ${price(item.take_profit)}`);
      cell(row, money(item.profit), pnlClass(item.profit));
      cell(row, dateTime(item.open_time));
      body.appendChild(row);
    });
  }

  function renderOrders(orders) {
    const body = byId('orders-body');
    setText('orders-badge', `${orders.length} pending`);
    if (!orders.length) return emptyRow(body, 7, 'No pending orders right now.');
    body.replaceChildren();
    orders.forEach((item) => {
      const row = document.createElement('tr');
      cell(row, item.ea, 'table-ea');
      cell(row, item.symbol, 'font-mono');
      cell(row, item.type);
      cell(row, number(item.volume, 2));
      cell(row, price(item.price));
      cell(row, `${price(item.stop_loss)} / ${price(item.take_profit)}`);
      cell(row, dateTime(item.placed_time));
      body.appendChild(row);
    });
  }

  function renderEaSummary(items) {
    const body = byId('ea-summary-body');
    if (!items.length) return emptyRow(body, 8, 'No EA-attributed trades are available yet.');
    body.replaceChildren();
    items.forEach((item) => {
      const row = document.createElement('tr');
      cell(row, item.ea, 'table-ea');
      cell(row, String(item.magic), 'font-mono');
      cell(row, item.symbols.join(', '));
      cell(row, String(item.closed_trades));
      cell(row, item.win_rate == null ? '—' : `${number(item.win_rate)}%`);
      cell(row, money(item.net_profit), pnlClass(item.net_profit));
      cell(row, String(item.open_positions));
      cell(row, money(item.floating_profit), pnlClass(item.floating_profit));
      body.appendChild(row);
    });
  }

  function updateTradeFilter(trades) {
    const select = byId('trade-ea-filter');
    const selected = select.value;
    const names = [...new Set(trades.map((trade) => trade.ea))].sort();
    select.replaceChildren(new Option('All EAs', 'all'));
    names.forEach((name) => select.add(new Option(name, name)));
    select.value = names.includes(selected) ? selected : 'all';
  }

  function renderTrades() {
    const body = byId('trades-body');
    const query = byId('trade-search').value.trim().toLowerCase();
    const selectedEa = byId('trade-ea-filter').value;
    const filtered = state.trades.filter((item) => {
      const haystack = `${item.ea} ${item.symbol} ${item.position_id} ${item.entry_comment} ${item.exit_comment}`.toLowerCase();
      return (!query || haystack.includes(query)) && (selectedEa === 'all' || item.ea === selectedEa);
    });
    setText('trades-badge', `${filtered.length} of ${state.trades.length} trades`);
    if (!filtered.length) return emptyRow(body, 9, 'No closed trades match this filter.');
    body.replaceChildren();
    filtered.forEach((item) => {
      const row = document.createElement('tr');
      cell(row, dateTime(item.close_time));
      const ea = cell(row, item.ea, 'table-ea');
      const meta = document.createElement('small');
      meta.textContent = `magic ${item.magic} · #${item.position_id}`;
      ea.appendChild(meta);
      cell(row, item.symbol, 'font-mono');
      cell(row, item.side, item.side === 'Buy' ? 'side-buy' : 'side-sell');
      cell(row, number(item.volume, 2));
      cell(row, `${price(item.open_price)} → ${price(item.close_price)}`);
      cell(row, money(item.costs), item.costs < 0 ? 'pnl-negative' : '');
      cell(row, money(item.net_profit), pnlClass(item.net_profit));
      const exit = cell(row, item.exit_comment || duration(item.duration_seconds));
      exit.title = `${duration(item.duration_seconds)} · ${item.entry_comment || 'No entry comment'}`;
      body.appendChild(row);
    });
  }

  function svgNode(name, attributes = {}, text = '') {
    const node = document.createElementNS('http://www.w3.org/2000/svg', name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text) node.textContent = text;
    return node;
  }

  function curveSinceAugust(data) {
    const start = new Date('2026-08-01T00:00:00Z');
    const backend = (data.equity_series || []).filter((point) => new Date(point.time) >= start);
    if (backend.some((point) => new Date(point.time).getTime() <= start.getTime() + 60000)) return backend;

    const closed = (data.trades || [])
      .filter((trade) => trade.close_time && new Date(trade.close_time) >= start)
      .sort((first, second) => new Date(first.close_time) - new Date(second.close_time));
    let balance = Number(data.account?.balance || 0) - closed.reduce((total, trade) => total + Number(trade.net_profit || 0), 0);
    const history = [{ time: start.toISOString(), balance, equity: null, floating: null, source: 'client-reconstructed-history' }];
    closed.forEach((trade) => {
      balance += Number(trade.net_profit || 0);
      history.push({ time: trade.close_time, balance, equity: null, floating: null, source: 'client-reconstructed-history' });
    });
    return [...history, ...backend].sort((first, second) => new Date(first.time) - new Date(second.time));
  }

  function curveSinceFirstTenK(data) {
    const complete = curveSinceAugust(data);
    const crossing = complete.findIndex((point, index) => (
      Number(point.balance) >= 10000 && (index === 0 || Number(complete[index - 1].balance) < 10000)
    ));
    if (crossing < 0) return complete;
    if (crossing === 0) return complete;
    const previous = complete[crossing - 1];
    const current = complete[crossing];
    const low = Number(previous.balance), high = Number(current.balance);
    const ratio = high === low ? 1 : Math.max(0, Math.min(1, (10000 - low) / (high - low)));
    const previousTime = new Date(previous.time).getTime();
    const currentTime = new Date(current.time).getTime();
    const anchor = {
      time: new Date(previousTime + (currentTime - previousTime) * ratio).toISOString(),
      balance: 10000,
      equity: null,
      floating: null,
      source: 'first-10k-ledger-crossing',
    };
    return [anchor, ...complete.slice(crossing)];
  }

  function renderChart(series) {
    const svg = byId('equity-chart');
    const empty = byId('chart-empty');
    if (!series || series.length < 2) {
      svg.classList.add('hidden');
      empty.classList.remove('hidden');
      return;
    }
    empty.classList.add('hidden');
    svg.classList.remove('hidden');
    svg.replaceChildren();
    const width = 1000, height = 320, left = 72, right = 20, top = 22, bottom = 38;
    const values = series.flatMap((point) => {
      const result = [Number(point.balance)];
      if (point.equity != null) result.push(Number(point.equity));
      return result;
    });
    let min = Math.min(...values), max = Math.max(...values);
    const padding = Math.max((max - min) * 0.12, 1);
    min -= padding; max += padding;
    const timestamps = series.map((point) => new Date(point.time).getTime());
    const firstTimestamp = Math.min(...timestamps), lastTimestamp = Math.max(...timestamps);
    const timeSpan = Math.max(lastTimestamp - firstTimestamp, 1);
    const x = (point) => left + (new Date(point.time).getTime() - firstTimestamp) / timeSpan * (width - left - right);
    const y = (value) => top + (max - value) / (max - min) * (height - top - bottom);
    for (let index = 0; index < 5; index += 1) {
      const yy = top + index / 4 * (height - top - bottom);
      const value = max - index / 4 * (max - min);
      svg.appendChild(svgNode('line', { x1: left, y1: yy, x2: width - right, y2: yy, stroke: 'rgba(255,255,255,.09)', 'stroke-width': 1 }));
      svg.appendChild(svgNode('text', { x: left - 10, y: yy + 4, fill: '#789089', 'font-size': 11, 'text-anchor': 'end' }, money(value)));
    }
    const balancePoints = series.map((point) => `${x(point)},${y(Number(point.balance))}`).join(' ');
    const recordedEquity = series.filter((point) => point.equity != null);
    const equityPoints = recordedEquity.map((point) => `${x(point)},${y(Number(point.equity))}`).join(' ');
    svg.appendChild(svgNode('polyline', { points: balancePoints, fill: 'none', stroke: '#63d9ff', 'stroke-width': 2, 'stroke-linejoin': 'round' }));
    if (recordedEquity.length >= 2) {
      svg.appendChild(svgNode('polyline', { points: equityPoints, fill: 'none', stroke: '#7ef7c7', 'stroke-width': 3, 'stroke-linejoin': 'round' }));
    } else if (recordedEquity.length === 1) {
      svg.appendChild(svgNode('circle', { cx: x(recordedEquity[0]), cy: y(Number(recordedEquity[0].equity)), r: 4, fill: '#7ef7c7' }));
    }
    svg.appendChild(svgNode('text', { x: left, y: height - 10, fill: '#789089', 'font-size': 11 }, dateTime(series[0].time)));
    svg.appendChild(svgNode('text', { x: width - right, y: height - 10, fill: '#789089', 'font-size': 11, 'text-anchor': 'end' }, dateTime(series.at(-1).time)));
  }

  function renderSnapshot(data) {
    state.data = data;
    const dot = byId('live-dot');
    dot.classList.toggle('connected', Boolean(data.connected));
    setText('live-status', data.connected ? 'Live · MT5 connected' : 'MT5 disconnected');
    setText('live-updated', data.last_update ? `Updated ${dateTime(data.last_update)}` : 'Waiting for first snapshot');
    const error = byId('live-error');
    error.classList.toggle('hidden', Boolean(data.connected));
    error.textContent = data.connected ? '' : `${data.message} Keep the MT5 terminal open and logged in; this page reconnects automatically.`;
    if (!data.account) return;
    const account = data.account;
    state.currency = account.currency || 'USD';
    setMoney('stat-balance', account.balance);
    setMoney('stat-equity', account.equity);
    setMoney('stat-floating', account.floating_profit);
    setMoney('stat-closed', account.closed_net_profit);
    setMoney('stat-free-margin', account.margin_free);
    setText('stat-equity-delta', `${money(account.equity - account.balance)} versus balance`);
    setText('stat-margin-level', `Margin level ${number(account.margin_level)}%`);
    setText('history-start', `History since ${dateTime(account.history_started)}`);
    setText('account-id', `${account.login} · ${account.server}`);
    setText('meta-account', account.login);
    setText('meta-server', account.server);
    setText('meta-currency', account.currency);
    setText('meta-leverage', `1:${account.leverage}`);
    setText('meta-monitoring', dateTime(data.monitoring_started));
    renderPositions(data.positions || []);
    renderOrders(data.orders || []);
    renderEaSummary(data.ea_summary || []);
    state.trades = data.trades || [];
    updateTradeFilter(state.trades);
    renderTrades();
    renderChart(curveSinceFirstTenK(data));
  }

  async function refresh() {
    try {
      const response = await fetch('/api/live/portfolio', { cache: 'no-store' });
      if (!response.ok) throw new Error(`Live endpoint returned ${response.status}`);
      renderSnapshot(await response.json());
    } catch (error) {
      byId('live-dot').classList.remove('connected');
      setText('live-status', 'Live dashboard unavailable');
      setText('live-updated', String(error));
    }
  }

  byId('trade-search')?.addEventListener('input', renderTrades);
  byId('trade-ea-filter')?.addEventListener('change', renderTrades);
  refresh();
  window.setInterval(refresh, 5000);
})();
