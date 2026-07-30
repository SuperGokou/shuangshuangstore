const DATA_URL = 'data/junanex-orders.json';

let state = {
  source: null,
  orders: [],
  activeView: 'overview',
  statusFilter: 'all',
  query: '',
};

const viewTitles = {
  overview: '全部包裹',
  not_submitted: '未发往库房',
  processing: '库房处理中',
  departed: '已运往中国',
  attention: '需要处理',
};

const actionTextPatterns = [
  '复制物流信息网址',
  '完整物流信息',
  '确认客户已收货',
  '有身份证号',
  '有身份证图片',
];

const deliveredPatterns = ['客户已收货', '已派送', '已签收', '签收成功', '派送成功'];
const attentionPatterns = ['异常', '失败', '退回', '问题'];
const junkTrackingPatterns = ['君安相伴', '运单追踪', '追踪运单号', '芝加哥电话', '波特兰电话'];

document.addEventListener('DOMContentLoaded', () => {
  bindControls();
  loadData();
});

function bindControls() {
  document.querySelectorAll('[data-view], [data-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      const view = button.dataset.view || button.dataset.filter;
      state.activeView = view || 'overview';
      syncActiveButtons();
      render();
    });
  });

  document.getElementById('status-filter')?.addEventListener('change', (event) => {
    state.statusFilter = event.target.value;
    render();
  });

  document.getElementById('search-input')?.addEventListener('input', (event) => {
    state.query = event.target.value.trim().toLowerCase();
    render();
  });

  document.getElementById('download-json')?.addEventListener('click', () => {
    const blob = new Blob([JSON.stringify(state.source || {}, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `junanex-orders-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });
}

async function loadData() {
  try {
    const response = await fetch(DATA_URL, { cache: 'no-store' });
    if (!response.ok) throw new Error('No real generated data');
    state.source = await response.json();
    document.getElementById('data-warning').hidden = true;
  } catch (error) {
    state.source = {
      generated_at: null,
      source: 'junanex',
      orders: [],
      error: error.message,
    };
    document.getElementById('data-warning').hidden = false;
  }

  state.orders = Array.isArray(state.source.orders) ? state.source.orders : [];
  render();
}

function render() {
  renderMetrics();
  renderTimestamp();
  renderTable();
}

function renderMetrics() {
  setText('metric-total', state.orders.length);
  setText('metric-not-submitted', countByStage('not_submitted'));
  setText('metric-processing', countByStage('processing'));
  setText('metric-departed', countByStage('departed'));
  setText('metric-attention', state.orders.filter((order) => classify(order) === 'attention').length);
}

function renderTimestamp() {
  const raw = state.source?.generated_at;
  const date = raw ? new Date(raw) : null;
  const text = date && !Number.isNaN(date.valueOf()) ? date.toLocaleString() : '未生成数据';
  setText('last-sync', text);
}

function renderTable() {
  const rows = filteredOrders();
  setText('panel-title', viewTitles[state.activeView] || '全部包裹');
  setText('panel-summary', `${rows.length} 条显示 · 共 ${state.orders.length} 条 · ${state.source?.source || 'local JSON'}`);

  const tbody = document.getElementById('orders-body');
  tbody.innerHTML = '';
  if (!rows.length) {
    tbody.appendChild(document.getElementById('empty-template').content.cloneNode(true));
    return;
  }

  rows.forEach((order) => {
    const tr = document.createElement('tr');
    const stage = stageOf(order);
    const trackingEvents = normalizeTrackingEvents(order.tracking_history || order.detail_events || []);
    const statusType = classify(order, trackingEvents);
    const latest = latestLogistics(order, trackingEvents);
    const timeline = renderTimeline(trackingEvents.slice(1));
    const trackingUrl = order.tracking_page_url || order.detail_url || order.tracking_url || '';
    const copyUrl = order.copy_logistics_url || trackingUrl;
    const recipientPhone = firstValue(order, ['recipient_phone', 'phone', 'mobile', 'telephone']);
    const recipientAddress = firstValue(order, ['recipient_address', 'address', 'shipping_address', 'delivery_address']);
    tr.className = `order-row ${statusType}`;

    tr.innerHTML = `
      <td>
        <div class="order-code">${escapeHtml(order.local_order_number || order.order_number || order.tracking_number || '未知单号')}</div>
        <div class="pill-row">${stageLabels(order).map((label) => `<span class="pill ${label.key}">${escapeHtml(label.text)}</span>`).join('')}</div>
      </td>
      <td class="recipient">
        <strong>${escapeHtml(order.recipient_name || order.recipient_summary || '-')}</strong>
        <span class="muted small">${escapeHtml(order.recipient_region || '')}</span>
        <div class="contact-stack">
          <span class="${recipientPhone ? 'contact-line' : 'muted small'}">电话：${escapeHtml(recipientPhone || '未抓到')}</span>
          <span class="${recipientAddress ? 'address-line' : 'muted small'}">地址：${escapeHtml(recipientAddress || '未抓到')}</span>
        </div>
        <div class="pill-row">${order.has_id_number ? '<span class="pill delivered">有身份证号</span>' : ''}${order.has_id_image ? '<span class="pill delivered">有身份证图片</span>' : ''}</div>
      </td>
      <td class="status-text">
        <span class="pill ${statusType}">${statusText(statusType)}</span>
        <div class="latest-line">${escapeHtml(latest.status)}</div>
        ${latest.time ? `<time class="latest-time">${escapeHtml(latest.time)}</time>` : ''}
        ${timeline}
      </td>
      <td class="items">
        <strong>${escapeHtml(order.item_summary || order.items_detail || '-')}</strong>
        <span class="muted small">${escapeHtml(order.domestic_tracking || '')}</span>
      </td>
      <td class="money">
        <strong>${escapeHtml(formatWeight(order.actual_weight || order.actual_weight_lb))}</strong>
        <span class="muted small">计费 ${escapeHtml(formatWeight(order.billing_weight || order.billing_weight_lb))}</span>
        <span class="muted small">扣费 ${escapeHtml(formatFee(order.total_fee || order.fee))}</span>
      </td>
      <td>
        <div class="actions">
          ${trackingUrl ? `<a class="primary-action" href="${escapeAttr(trackingUrl)}" target="_blank" rel="noreferrer">完整物流</a>` : '<button type="button" disabled>无物流页</button>'}
          ${copyUrl ? `<button type="button" data-copy="${escapeAttr(copyUrl)}">复制物流链接</button>` : ''}
        </div>
      </td>
    `;

    tr.querySelector('[data-copy]')?.addEventListener('click', async (event) => {
      const url = event.currentTarget.dataset.copy;
      await navigator.clipboard.writeText(url);
      event.currentTarget.textContent = '已复制';
      setTimeout(() => { event.currentTarget.textContent = '复制物流链接'; }, 1200);
    });

    tbody.appendChild(tr);
  });
}

function renderTimeline(events) {
  const cleanEvents = normalizeTrackingEvents(events).slice(0, 3);
  if (!cleanEvents.length) return '<div class="timeline"><div><p>暂无完整物流明细，运行抓取器后会从 tracking 页补齐。</p></div></div>';
  return `
    <div class="timeline">
      ${cleanEvents.map((event) => `
        <div>
          <time>${escapeHtml(event.time || '')}</time>
          <p>${escapeHtml(event.status || event.text || '')}</p>
        </div>
      `).join('')}
    </div>
  `;
}

function filteredOrders() {
  return state.orders
    .filter((order) => state.activeView === 'overview' || matchesStage(order, state.activeView))
    .filter((order) => state.statusFilter === 'all' || matchesStage(order, state.statusFilter))
    .filter((order) => !state.query || searchableText(order).includes(state.query));
}

function matchesStage(order, wanted) {
  const statusType = classify(order);
  if (wanted === 'attention') return statusType === 'attention';
  if (wanted === 'delivered') return statusType === 'delivered';
  if (wanted === 'departed') return stageOf(order) === 'departed' || statusType === 'departed';
  if (wanted === 'processing') return stageOf(order) === 'processing';
  if (wanted === 'not_submitted') return stageOf(order) === 'not_submitted';
  return true;
}

function countByStage(stage) {
  return state.orders.filter((order) => stageOf(order) === stage).length;
}

function stageOf(order) {
  const raw = [
    order.stage,
    order.source_category,
    ...(order.categories || []),
    order.page_label,
    order.order_status,
    order.latest_status,
  ].join(' ').toLowerCase();
  if (raw.includes('not_submitted') || raw.includes('未发往库房') || raw.includes('未发往')) return 'not_submitted';
  if (raw.includes('processing') || raw.includes('库房处理中') || raw.includes('处理中')) return 'processing';
  if (raw.includes('departed') || raw.includes('已运往中国') || raw.includes('运往中国') || raw.includes('发往中国')) return 'departed';
  return 'not_submitted';
}

function classify(order, trackingEvents = normalizeTrackingEvents(order.tracking_history || order.detail_events || [])) {
  const text = statusSearchText(order, trackingEvents);
  if (!order.tracking_page_url && !order.detail_url && !order.tracking_url) return 'attention';
  if (includesAny(text, attentionPatterns)) return 'attention';
  if (includesAny(text, deliveredPatterns)) return 'delivered';
  if (stageOf(order) === 'departed') return 'departed';
  if (stageOf(order) === 'processing') return 'processing';
  return 'not_submitted';
}

function statusText(type) {
  return {
    attention: '需要处理',
    delivered: '客户已收货',
    departed: '运输中',
    processing: '库房处理中',
    not_submitted: '未发往库房',
  }[type] || '待确认';
}

function stageLabels(order) {
  const stage = stageOf(order);
  const labels = [{ key: stage, text: viewTitles[stage] || stage }];
  if (order.domestic_tracking) labels.push({ key: 'departed', text: '国内快递' });
  return labels;
}

function searchableText(order) {
  return [
    order.local_order_number,
    order.order_number,
    order.tracking_number,
    order.tracking_page_url,
    order.recipient_name,
    order.recipient_region,
    order.recipient_summary,
    order.recipient_phone,
    order.phone,
    order.mobile,
    order.recipient_address,
    order.address,
    order.shipping_address,
    order.order_status,
    order.latest_status,
    order.item_summary,
    order.items_detail,
    order.domestic_tracking,
    stripActionText(order.raw_text),
    ...(order.tracking_history || []).map((event) => stripActionText(event?.status || event?.text || '')),
  ].join(' ').toLowerCase();
}

function statusSearchText(order, trackingEvents) {
  return [
    order.order_status,
    order.latest_status,
    ...trackingEvents.map((event) => `${event.time || ''} ${event.status || ''}`),
  ].map(stripActionText).join(' ').toLowerCase();
}

function stripActionText(value) {
  let text = String(value ?? '').replace(/\s+/g, ' ').trim();
  actionTextPatterns.forEach((phrase) => {
    text = text.split(phrase).join(' ');
  });
  return text.replace(/\s+/g, ' ').trim();
}

function includesAny(text, patterns) {
  return patterns.some((pattern) => text.includes(pattern.toLowerCase()));
}

function normalizeTrackingEvents(events) {
  const seen = new Set();
  return (events || [])
    .map((event) => ({
      time: String(event?.time || '').trim(),
      status: stripActionText(event?.status || event?.text || ''),
    }))
    .filter((event) => event.status && event.status.length <= 180)
    .filter((event) => !junkTrackingPatterns.some((pattern) => event.status.includes(pattern)))
    .sort((a, b) => eventTimeValue(b.time) - eventTimeValue(a.time))
    .filter((event) => {
      const key = `${event.time}|${event.status}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function latestLogistics(order, trackingEvents) {
  const latestEvent = trackingEvents[0];
  if (latestEvent?.status) {
    return { status: latestEvent.status, time: latestEvent.time || '' };
  }

  const fallback = stripActionText(order.latest_status || order.order_status || '');
  return {
    status: fallback || '-',
    time: order.latest_time || '',
  };
}

function eventTimeValue(value) {
  if (!value) return 0;
  const normalized = String(value)
    .replace(/年|\/|月/g, '-')
    .replace(/日/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  const timestamp = Date.parse(normalized.replace(/-/g, '/'));
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function firstValue(source, fields) {
  for (const field of fields) {
    const value = source?.[field];
    if (value !== undefined && value !== null && String(value).trim()) {
      return String(value).trim();
    }
  }
  return '';
}

function syncActiveButtons() {
  document.querySelectorAll('[data-view], [data-filter]').forEach((button) => {
    const value = button.dataset.view || button.dataset.filter;
    button.classList.toggle('active', value === state.activeView);
  });
}

function formatWeight(value) {
  if (value === undefined || value === null || value === '') return '-';
  return `${value} lb`;
}

function formatFee(value) {
  if (value === undefined || value === null || value === '') return '-';
  return `$${value}`;
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = String(value);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, '&#96;');
}
