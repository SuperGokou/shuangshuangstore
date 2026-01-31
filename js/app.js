// ========== NAVIGATION ==========
const navItems = document.querySelectorAll('.nav-item[data-page]');
const pages = document.querySelectorAll('.page');
const hamburgerBtn = document.getElementById('hamburger');
const sidebarEl = document.getElementById('sidebar');
const overlayEl = document.getElementById('sidebar-overlay');

function navigateTo(pageId) {
    pages.forEach(p => p.classList.add('hidden'));
    navItems.forEach(n => n.classList.remove('active'));
    const target = document.getElementById('page-' + pageId);
    if (target) target.classList.remove('hidden');
    const navEl = document.querySelector(`.nav-item[data-page="${pageId}"]`);
    if (navEl) navEl.classList.add('active');
    sidebarEl.classList.remove('open');
    overlayEl.classList.remove('open');
    window.scrollTo(0, 0);
}

navItems.forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        navigateTo(item.dataset.page);
    });
});

hamburgerBtn.addEventListener('click', () => {
    sidebarEl.classList.toggle('open');
    overlayEl.classList.toggle('open');
});
overlayEl.addEventListener('click', () => {
    sidebarEl.classList.remove('open');
    overlayEl.classList.remove('open');
});

// ========== INVENTORY VIEW MODE ==========
let currentView = 'table';
function setInventoryView(mode) {
    currentView = mode;
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.view-btn[data-view="${mode}"]`).classList.add('active');
    document.getElementById('inv-table-view').style.display = mode === 'table' ? '' : 'none';
    document.getElementById('inv-grid-view').style.display = mode === 'grid' ? '' : 'none';
    document.getElementById('inv-list-view').style.display = mode === 'list' ? '' : 'none';
}

// ========== DATA STORE ==========
let allProducts = [];
let allStats = [];
let allOrders = [];
let allShipping = [];
let purchaseOrders = [];
let financeData = [];

// ========== FETCH ALL DATA ==========
Promise.all([
    fetch('data/products.json').then(r => r.ok ? r.json() : []),
    fetch('data/stats.json').then(r => r.ok ? r.json() : []),
    fetch('data/orders.json').then(r => r.ok ? r.json() : []),
    fetch('data/shipping.json').then(r => r.ok ? r.json() : []),
    fetch('data/purchase_orders.json').then(r => r.ok ? r.json() : []),
    fetch('data/finance.json').then(r => r.ok ? r.json() : [])
]).then(([products, stats, orders, shipping, purchases, finance]) => {
    allProducts = products;
    allStats = stats;
    allOrders = orders;
    allShipping = shipping;
    purchaseOrders = purchases;
    financeData = finance;

    renderDashboard();
    renderInventoryPage();
    renderPurchasePage();
    renderShippingPage();
    renderAnalyticsPage();
}).catch(err => console.error("Data load error:", err));

// ========== DASHBOARD FILTER ==========
let dashboardFilter = null; // null = show all, or 'us_signed' | 'us_unsigned' | 'shipped_cn' | 'total_stock'

const filterLabels = {
    us_signed: 'US Signed (美国签收)',
    us_unsigned: 'US Unsigned (美国未签)',
    shipped_cn: 'In Transit to China (发往中国)',
    total_stock: 'Total Stock (商品总数)'
};

const filterTitles = {
    us_signed: { tag: 'US Signed', title: '美国签收产品', desc: 'Products with US signed inventory' },
    us_unsigned: { tag: 'US Unsigned', title: '美国未签产品', desc: 'Products with unsigned US inventory' },
    shipped_cn: { tag: 'In Transit', title: '发往中国产品', desc: 'Products shipped to China' },
    total_stock: { tag: 'Total', title: '所有库存产品', desc: 'All products with stock' }
};

function toggleDashboardFilter(key) {
    if (dashboardFilter === key) {
        dashboardFilter = null;
    } else {
        dashboardFilter = key;
    }
    // Update active state on cards
    document.querySelectorAll('#metrics-row .metric-card').forEach(card => {
        card.classList.toggle('active', card.dataset.filter === dashboardFilter);
    });
    // Update filter info bar
    const infoEl = document.getElementById('dashboard-filter-info');
    if (dashboardFilter) {
        const filtered = allProducts.filter(p => (p[dashboardFilter] || 0) > 0);
        infoEl.innerHTML = `Showing <strong>${filtered.length}</strong> products with ${filterLabels[dashboardFilter]} <span class="dashboard-filter-clear" onclick="toggleDashboardFilter('${dashboardFilter}')">&times; Clear</span>`;
        infoEl.classList.remove('hidden');
    } else {
        infoEl.classList.add('hidden');
    }
    updateDashboardMainCard();
}

function updateDashboardMainCard() {
    const ordersView = document.getElementById('dashboard-orders-view');
    const productsView = document.getElementById('dashboard-products-view');
    const titleEl = document.getElementById('dashboard-main-title');
    const descEl = document.getElementById('dashboard-main-desc');

    if (!dashboardFilter) {
        // Show orders
        ordersView.style.display = '';
        productsView.style.display = 'none';
        titleEl.innerHTML = '<span class="section-tag">Orders</span> 采购订单追踪';
        descEl.textContent = 'Incoming orders tracking';
    } else {
        // Show filtered products
        ordersView.style.display = 'none';
        productsView.style.display = '';
        const info = filterTitles[dashboardFilter];
        titleEl.innerHTML = `<span class="section-tag">${info.tag}</span> ${info.title}`;
        descEl.textContent = info.desc;
        renderFilteredProducts();
    }
}

function renderFilteredProducts() {
    const thead = document.getElementById('filtered-products-thead');
    const tbody = document.getElementById('filtered-products-body');
    const products = allProducts.filter(p => (p[dashboardFilter] || 0) > 0);

    // Column config per filter
    const valueLabel = {
        us_signed: '签收数量',
        us_unsigned: '未签数量',
        shipped_cn: '发货数量',
        total_stock: '库存总数'
    };

    thead.innerHTML = `<tr>
        <th class="col-thumb-lg">图片</th>
        <th>产品名称 (Product)</th>
        <th>${valueLabel[dashboardFilter]}</th>
        <th>美国签收</th>
        <th>美国未签</th>
        <th>发往中国</th>
        <th>总库存</th>
    </tr>`;

    tbody.innerHTML = '';
    if (products.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No matching products.</td></tr>';
        return;
    }

    // Sort by the filtered value descending
    products.sort((a, b) => (b[dashboardFilter] || 0) - (a[dashboardFilter] || 0));

    products.forEach(product => {
        const row = document.createElement('tr');
        const safeImg = encodeURI(product.image || '');
        const val = product[dashboardFilter] || 0;
        row.innerHTML = `
            <td>
                <div class="image-wrapper thumb-cell-48">
                    <img src="${safeImg}" alt="${product.name}"
                         onerror="this.src='https://via.placeholder.com/48?text=?'">
                </div>
            </td>
            <td class="cell-bold">${product.name}</td>
            <td class="cell-filter-value">${val}</td>
            <td class="cell-green">${product.us_signed || 0}</td>
            <td class="cell-amber">${product.us_unsigned || 0}</td>
            <td>${product.shipped_cn || 0}</td>
            <td class="cell-total">${product.total_stock || 0}</td>
        `;
        tbody.appendChild(row);
    });
}

// ========== DASHBOARD ==========
function renderDashboard() {
    let totalSigned = 0, totalUnsigned = 0, totalShippedCn = 0, totalStock = 0;
    allProducts.forEach(product => {
        totalSigned += (product.us_signed || 0);
        totalUnsigned += (product.us_unsigned || 0);
        totalShippedCn += (product.shipped_cn || 0);
        totalStock += (product.total_stock || 0);
    });

    document.getElementById('metric-us-signed').textContent = totalSigned.toLocaleString();
    document.getElementById('metric-us-unsigned').textContent = totalUnsigned.toLocaleString();
    document.getElementById('metric-shipped-cn').textContent = totalShippedCn.toLocaleString();
    document.getElementById('metric-total-stock').textContent = totalStock.toLocaleString();

    renderOrdersTable();
    renderShippingCostChart();
}

function renderStatsTable(tbodyId, stats) {
    const tbody = document.getElementById(tbodyId);
    if (stats.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8">No stats available</td></tr>';
        return;
    }
    stats.forEach(item => {
        const row = document.createElement('tr');
        const safeImg = encodeURI(item.image || '');
        row.innerHTML = `
            <td>
                <div class="image-wrapper thumb-cell">
                    <img src="${safeImg}" alt="img"
                         onerror="this.src='https://via.placeholder.com/50?text=?'">
                </div>
            </td>
            <td class="cell-bold">${item['产品名称']}</td>
            <td class="cell-total">${item['已发总数']}</td>
            <td class="cell-green">${item['带包装']}</td>
            <td class="cell-detail">${item['带包装详情']}</td>
            <td class="cell-red">${item['不带包装']}</td>
            <td class="cell-detail">${item['不带包装详情']}</td>
            <td class="cell-total">${item['总库存']}</td>
        `;
        tbody.appendChild(row);
    });
}

function renderOrdersTable() {
    const tbody = document.getElementById('order-body');
    if (allOrders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">No orders found.</td></tr>';
        return;
    }
    allOrders.forEach(order => {
        const row = document.createElement('tr');
        const statusMap = {
            'Fulfilled': 'badge-fulfilled', 'Shipped': 'badge-fulfilled',
            'Partial': 'badge-partial', 'In Transit': 'badge-transit',
            'Pending': 'badge-pending'
        };
        const badgeClass = statusMap[order.status] || 'badge-pending';
        let signedText = order.signed;
        let signedClass = 'signed-yes';
        if (String(signedText).includes('No') || String(signedText).includes('否')) {
            signedClass = 'signed-no';
        }
        let trackingDisplay = order.tracking;
        if (order.tracking_url && order.tracking !== '——' && order.tracking !== '-') {
            trackingDisplay = `<a href="${order.tracking_url}" target="_blank">${order.tracking}</a>`;
        }
        const sourceDotClass = order.source.toLowerCase().includes('stanley') ? 'stanley' :
                               order.source.toLowerCase().includes('love') ? 'loveshack' : 'default';
        row.innerHTML = `
            <td><span class="source-dot ${sourceDotClass}"></span>${order.source}</td>
            <td>${order.order_id}</td>
            <td><span class="badge ${badgeClass}">${order.status}</span></td>
            <td class="tracking-code">${trackingDisplay}</td>
            <td class="${signedClass}">${signedText}</td>
            <td>${order.est_date || '——'}</td>
        `;
        tbody.appendChild(row);
    });
}

// ========== SHIPPING COST CHART ==========
function renderShippingCostChart() {
    const container = document.getElementById('shipping-cost-chart');
    const summaryEl = document.getElementById('shipping-cost-summary');
    if (!container) return;

    // Build deposit/refund lookup from finance.json
    const deposits = {};
    const refunds = {};
    financeData.forEach(f => {
        if (f.month) {
            deposits[f.month] = (deposits[f.month] || 0) + (parseFloat(f.deposit) || 0);
            refunds[f.month] = (refunds[f.month] || 0) + (parseFloat(f.refund) || 0);
        }
    });

    // Aggregate cost & weight from allShipping by month
    const monthlyAgg = {};
    allShipping.forEach(s => {
        if (!s.date || !s.fee) return;
        // Support date formats: "YYYY-MM-DD", "MM/DD/YYYY", "YYYY/MM/DD", etc.
        const d = new Date(s.date);
        if (isNaN(d.getTime())) return;
        const key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
        if (!monthlyAgg[key]) monthlyAgg[key] = { cost: 0, weight: 0 };
        monthlyAgg[key].cost += parseFloat(s.fee) || 0;
        monthlyAgg[key].weight += parseFloat(s.weight) || 0;
    });

    // Build last 6 months ending at current month
    const now = new Date();
    const data = [];
    const monthNames = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
    for (let i = 5; i >= 0; i--) {
        const m = new Date(now.getFullYear(), now.getMonth() - i, 1);
        const key = m.getFullYear() + '-' + String(m.getMonth() + 1).padStart(2, '0');
        const agg = monthlyAgg[key] || { cost: 0, weight: 0 };
        data.push({
            label: monthNames[m.getMonth()],
            cost: Math.round(agg.cost * 100) / 100,
            deposit: deposits[key] || 0,
            refund: refunds[key] || 0,
            weight: Math.round(agg.weight * 100) / 100
        });
    }

    const thisMonth = data[data.length - 1];
    const lastMonth = data[data.length - 2];
    const totalCost = data.reduce((s, d) => s + d.cost, 0);
    const totalDeposit = data.reduce((s, d) => s + d.deposit, 0);
    const totalRefund = data.reduce((s, d) => s + d.refund, 0);
    const totalWeight = data.reduce((s, d) => s + d.weight, 0);
    const walletBalance = totalDeposit - totalCost + totalRefund;

    // Chart
    const allVals = data.flatMap(d => [d.cost, d.deposit, d.refund]);
    const maxVal = Math.max(...allVals, 1);
    const ceil = Math.ceil(maxVal / 500) * 500 || 500;
    const gridLines = 3;

    let gridHtml = '';
    for (let i = gridLines; i >= 0; i--) {
        const val = Math.round((ceil / gridLines) * i);
        const pct = (i / gridLines) * 100;
        gridHtml += `<div class="pkg-grid-line" style="bottom:${pct}%;"><span class="pkg-grid-label">${val}</span></div>`;
    }

    let barsHtml = '';
    data.forEach(d => {
        const costPct = (d.cost / ceil) * 100;
        const depositPct = (d.deposit / ceil) * 100;
        const refundPct = (d.refund / ceil) * 100;

        barsHtml += `
            <div class="pkg-bar-group">
                <div class="pkg-bars sc-bars-triple">
                    <div class="pkg-bar sc-bar-cost" style="height:${costPct}%;" title="运费: ${d.cost}"></div>
                    <div class="pkg-bar sc-bar-deposit" style="height:${depositPct}%;" title="支付: ${d.deposit}"></div>
                    <div class="pkg-bar sc-bar-refund" style="height:${refundPct}%;" title="退款: ${d.refund}"></div>
                </div>
                <div class="pkg-bar-label">${d.label}</div>
            </div>
        `;
    });

    container.innerHTML = `
        <div class="sc-legend">
            <div class="sc-legend-item"><span class="sc-legend-swatch sc-swatch-cost"></span> 运费</div>
            <div class="sc-legend-item"><span class="sc-legend-swatch sc-swatch-deposit"></span> 支付</div>
            <div class="sc-legend-item"><span class="sc-legend-swatch sc-swatch-refund"></span> 退款</div>
        </div>
        <div class="pkg-chart-wrapper">
            <div class="pkg-chart-area">
                ${gridHtml}
                <div class="pkg-bars-row">
                    ${barsHtml}
                </div>
            </div>
        </div>
    `;

    // Summary grid below chart
    if (summaryEl) {
        summaryEl.innerHTML = `
            <div class="sc-summary-col">
                <div class="sc-summary-title">本月统计</div>
                <div class="sc-summary-row"><span class="sc-summary-label">运费：</span>${thisMonth.cost.toFixed(1)}</div>
                <div class="sc-summary-row"><span class="sc-summary-label">支付：</span>${thisMonth.deposit.toFixed(1)}</div>
                <div class="sc-summary-row"><span class="sc-summary-label">退款：</span>${thisMonth.refund.toFixed(1)}</div>
                <div class="sc-summary-row"><span class="sc-summary-label">重量：</span>${thisMonth.weight.toFixed(1)} KG</div>
            </div>
            <div class="sc-summary-col">
                <div class="sc-summary-title">上月统计</div>
                <div class="sc-summary-row"><span class="sc-summary-label">运费：</span>${lastMonth.cost.toFixed(1)}</div>
                <div class="sc-summary-row"><span class="sc-summary-label">支付：</span>${lastMonth.deposit.toFixed(1)}</div>
                <div class="sc-summary-row"><span class="sc-summary-label">退款：</span>${lastMonth.refund.toFixed(1)}</div>
                <div class="sc-summary-row"><span class="sc-summary-label">重量：</span>${lastMonth.weight.toFixed(1)} KG</div>
            </div>
            <div class="sc-summary-col">
                <div class="sc-summary-title">近六个月合计</div>
                <div class="sc-summary-row"><span class="sc-summary-label">运费：</span>${totalCost.toFixed(1)}</div>
                <div class="sc-summary-row"><span class="sc-summary-label">支付：</span>${totalDeposit.toFixed(1)}</div>
                <div class="sc-summary-row"><span class="sc-summary-label">退款：</span>${totalRefund.toFixed(1)}</div>
                <div class="sc-summary-row"><span class="sc-summary-label">重量：</span>${totalWeight.toFixed(1)} KG</div>
            </div>
            <div class="sc-summary-col">
                <div class="sc-summary-title">钱包</div>
                <div class="sc-wallet-balance">${walletBalance.toFixed(2)} USD ▸</div>
            </div>
        `;
    }
}

// ========== INVENTORY PAGE ==========
function getInventoryStatus(product) {
    const stock = product.total_stock || 0;
    const unsigned = product.us_unsigned || 0;
    if (stock === 0) return { label: 'Out of Stock', class: 'badge-out-of-stock' };
    if (stock < 5) return { label: 'Low Stock', class: 'badge-low-stock' };
    if (unsigned > 0) return { label: 'In Transit', class: 'badge-transit' };
    return { label: 'In Stock', class: 'badge-in-stock' };
}

function getFilteredProducts() {
    const query = (document.getElementById('inv-search')?.value || '').toLowerCase();
    const sortBy = document.getElementById('inv-sort')?.value || 'name';

    let filtered = allProducts.filter(p =>
        !query || p.name.toLowerCase().includes(query)
    );

    filtered.sort((a, b) => {
        switch (sortBy) {
            case 'total-desc': return (b.total_stock || 0) - (a.total_stock || 0);
            case 'total-asc': return (a.total_stock || 0) - (b.total_stock || 0);
            case 'signed-desc': return (b.us_signed || 0) - (a.us_signed || 0);
            case 'status':
                const sa = getInventoryStatus(a).label;
                const sb = getInventoryStatus(b).label;
                return sa.localeCompare(sb);
            default: return a.name.localeCompare(b.name);
        }
    });
    return filtered;
}

function filterInventory() {
    renderInventoryViews(getFilteredProducts());
}

function renderInventoryPage() {
    let totalStock = 0, lowStock = 0, outOfStock = 0;
    allProducts.forEach(p => {
        const stock = p.total_stock || 0;
        totalStock += stock;
        if (stock === 0) outOfStock++;
        else if (stock < 5) lowStock++;
    });

    document.getElementById('inv-metric-skus').textContent = allProducts.length;
    document.getElementById('inv-metric-low').textContent = lowStock;
    document.getElementById('inv-metric-out').textContent = outOfStock;
    document.getElementById('inv-metric-total').textContent = totalStock.toLocaleString();

    renderInventoryViews(allProducts);
    renderStatsTable('inv-stats-body', allStats);
}

function renderInventoryViews(products) {
    document.getElementById('inv-count-info').textContent =
        `${products.length} of ${allProducts.length} products`;

    // Table view
    const tbody = document.getElementById('inventory-body');
    tbody.innerHTML = '';
    products.forEach(product => {
        const usSigned = product.us_signed || 0;
        const usUnsigned = product.us_unsigned || 0;
        const shippedCn = product.shipped_cn || 0;
        const stock = product.total_stock || 0;
        const safeImg = encodeURI(product.image || '');
        const status = getInventoryStatus(product);
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <div class="image-wrapper thumb-cell-48">
                    <img src="${safeImg}" alt="${product.name}"
                         onerror="this.src='https://via.placeholder.com/48?text=?'">
                </div>
            </td>
            <td class="cell-bold">${product.name}</td>
            <td class="cell-green">${usSigned}</td>
            <td class="cell-amber">${usUnsigned}</td>
            <td>${shippedCn}</td>
            <td class="cell-total">${stock}</td>
            <td><span class="badge ${status.class}">${status.label}</span></td>
        `;
        tbody.appendChild(row);
    });

    // Grid view
    const gridContainer = document.getElementById('inv-grid-view');
    gridContainer.innerHTML = '';
    products.forEach(product => {
        const safeImg = encodeURI(product.image || '');
        const status = getInventoryStatus(product);
        gridContainer.innerHTML += `
            <div class="grid-card">
                <img class="grid-card-img" src="${safeImg}" alt="${product.name}"
                     onerror="this.src='https://via.placeholder.com/240?text=No+Image'">
                <div class="grid-card-body">
                    <div class="grid-card-name">${product.name}</div>
                    <div class="grid-card-stats">
                        <span>US Signed: <strong>${product.us_signed || 0}</strong></span>
                        <span>US Unsigned: <strong>${product.us_unsigned || 0}</strong></span>
                        <span>In Transit: <strong>${product.shipped_cn || 0}</strong></span>
                        <span>Total: <strong>${product.total_stock || 0}</strong></span>
                    </div>
                    <div class="grid-card-footer">
                        <span class="badge ${status.class}">${status.label}</span>
                    </div>
                </div>
            </div>
        `;
    });

    // List view
    const listContainer = document.getElementById('inv-list-view');
    listContainer.innerHTML = '';
    products.forEach(product => {
        const safeImg = encodeURI(product.image || '');
        const status = getInventoryStatus(product);
        listContainer.innerHTML += `
            <div class="list-item">
                <img class="list-item-img" src="${safeImg}" alt="${product.name}"
                     onerror="this.src='https://via.placeholder.com/64?text=?'">
                <div class="list-item-info">
                    <div class="list-item-name">${product.name}</div>
                    <div class="list-item-meta">
                        <span>US Signed: <strong>${product.us_signed || 0}</strong></span>
                        <span>US Unsigned: <strong>${product.us_unsigned || 0}</strong></span>
                        <span>In Transit: <strong>${product.shipped_cn || 0}</strong></span>
                        <span>Total: <strong>${product.total_stock || 0}</strong></span>
                    </div>
                </div>
                <span class="badge ${status.class}">${status.label}</span>
            </div>
        `;
    });
}

function exportInventory() {
    alert('Export ' + allProducts.length + ' items to CSV');
}

// ========== PURCHASE ORDERS PAGE ==========
function toggleSignStatus(orderIndex, shipmentIndex, isChecked) {
    const order = purchaseOrders[orderIndex];
    if (!order || !order.shipments) return;
    const shipment = order.shipments[shipmentIndex];
    shipment.local_signed = isChecked ? 'Yes' : 'No';
    const uniqueKey = `${order.order_id}_${shipment.tracking_number}`;
    const savedState = JSON.parse(localStorage.getItem('purchase_signed_state') || '{}');
    if (isChecked) savedState[uniqueKey] = 'Yes';
    else delete savedState[uniqueKey];
    localStorage.setItem('purchase_signed_state', JSON.stringify(savedState));
}
window.toggleSignStatus = toggleSignStatus;

function renderPurchasePage() {
    const savedState = JSON.parse(localStorage.getItem('purchase_signed_state') || '{}');
    const tbody = document.getElementById('purchase-body');
    tbody.innerHTML = '';

    if (purchaseOrders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">No purchase history found.</td></tr>';
        return;
    }

    let totalItems = 0, totalShipments = 0, totalSigned = 0;
    const sources = new Set();

    purchaseOrders.forEach((order, orderIndex) => {
        sources.add(order.source);
        if (order.items) order.items.forEach(i => { totalItems += Math.abs(i.qty || 0); });
        if (order.shipments) {
            totalShipments += order.shipments.length;
            order.shipments.forEach(s => {
                const uniqueKey = `${order.order_id}_${s.tracking_number}`;
                const isSigned = savedState[uniqueKey] === 'Yes' || s.signed === 'Yes' || s.signed === '是';
                if (isSigned) totalSigned++;
            });
        }

        const row = document.createElement('tr');
        const sourceDotClass = order.source.toLowerCase().includes('stanley') ? 'stanley' :
                               order.source.toLowerCase().includes('love') ? 'loveshack' : 'default';

        let itemsHtml = '<div class="po-items-col">';
        if (order.items && order.items.length > 0) {
            order.items.forEach(item => {
                const safeImg = encodeURI(item.image || '');
                itemsHtml += `
                    <div class="po-item">
                        <div class="po-item-img">
                            <img src="${safeImg}" alt="img"
                                 onerror="this.src='https://via.placeholder.com/40?text=?'">
                        </div>
                        <div class="po-item-text">
                            <div class="po-item-name">${item.product}</div>
                            <div class="po-item-qty">Qty: <span class="po-item-qty-val">${item.qty}</span></div>
                        </div>
                    </div>
                `;
            });
        }
        itemsHtml += '</div>';

        let trackingHtml = '<span class="tracking-none">-</span>';
        if (order.shipments && order.shipments.length > 0) {
            trackingHtml = order.shipments.map((s, shipmentIndex) => {
                const fullNum = s.tracking_number;
                const uniqueKey = `${order.order_id}_${fullNum}`;
                let isSigned = false;
                if (savedState[uniqueKey]) {
                    isSigned = savedState[uniqueKey] === 'Yes';
                } else {
                    isSigned = s.signed === 'Yes' || s.signed === '是';
                }
                const checkedAttr = isSigned ? 'checked' : '';
                return `
                <div class="tracking-row">
                    <input type="checkbox"
                           class="tracking-checkbox"
                           ${checkedAttr}
                           onchange="toggleSignStatus(${orderIndex}, ${shipmentIndex}, this.checked)"
                           title="Mark as signed">
                    <span class="tracking-carrier">${s.carrier}:</span>
                    <a href="${s.tracking_url}" target="_blank" title="${fullNum}"
                       class="tracking-link">
                        ${fullNum}
                    </a>
                </div>`;
            }).join('');
        }

        let noteClass = 'note-default';
        const noteText = order.note || '';
        if (noteText.includes('已发货') && noteText.includes('已签收')) {
            noteClass = 'note-shipped-signed';
        } else if (noteText.includes('已发货') && noteText.includes('未签收')) {
            noteClass = 'note-shipped-unsigned';
        } else if (noteText.includes('退货')) {
            noteClass = 'note-returned';
        }

        row.innerHTML = `
            <td class="cell-date">${order.date}</td>
            <td>
                <div class="source-cell">
                    <span class="source-dot ${sourceDotClass}"></span>
                    <div>
                        <div class="source-name-bold">${order.source}</div>
                        <div class="source-id">${order.order_id}</div>
                    </div>
                </div>
            </td>
            <td class="cell-items-wrap">${itemsHtml}</td>
            <td>${trackingHtml}</td>
            <td class="${noteClass}">${order.note || '-'}</td>
        `;
        tbody.appendChild(row);
    });

    document.getElementById('po-metric-orders').textContent = purchaseOrders.length.toLocaleString();
    document.getElementById('po-metric-items').textContent = totalItems.toLocaleString();
    document.getElementById('po-metric-sources').textContent = sources.size.toLocaleString();
    document.getElementById('po-metric-shipments').textContent = totalShipments.toLocaleString();
    document.getElementById('po-metric-signed').textContent = totalSigned.toLocaleString();
}

function filterPurchaseOrders() {
    const query = (document.getElementById('po-search')?.value || '').toLowerCase();
    const rows = document.querySelectorAll('#purchase-body tr');
    rows.forEach(row => {
        row.style.display = !query || row.textContent.toLowerCase().includes(query) ? '' : 'none';
    });
}

function exportPurchaseOrders() {
    alert('Export ' + purchaseOrders.length + ' purchase orders to CSV');
}

// ========== SHIPPING PAGE ==========
function renderShippingPage() {
    const tbody = document.getElementById('shipping-body');
    if (allShipping.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No shipping data found.</td></tr>';
        return;
    }

    let totalWeight = 0;
    const recipients = new Set();

    allShipping.forEach(item => {
        const w = parseFloat(item.weight || item['实际重量'] || 0);
        totalWeight += isNaN(w) ? 0 : w;
        recipients.add(item.customer_name || item.recipient || '');

        const row = document.createElement('tr');
        const details = item.details || item['内件明细'] || '——';
        const weight = item.weight || item['实际重量'] || '——';
        let trackingDisplay = item.tracking_number;
        if (item.tracking_url) {
            trackingDisplay = `<a href="${item.tracking_url}" target="_blank">${item.tracking_number}</a>`;
        }
        let fullAddress = item.address || '';
        let displayAddress = fullAddress;
        if (fullAddress.length > 25) {
            displayAddress = fullAddress.substring(0, 9) + "......" + fullAddress.substring(fullAddress.length - 9);
        }
        let fullStatus = item.status || 'Checking...';
        let displayStatus = fullStatus;
        if (fullStatus.length > 16) {
            displayStatus = fullStatus.substring(0, 16) + '...';
        }
        let statusClass = 'badge-pending';
        const sl = fullStatus.toLowerCase();
        if (sl.includes('deliver') || sl.includes('签收')) statusClass = 'badge-delivered';
        else if (sl.includes('transit') || sl.includes('运输')) statusClass = 'badge-transit';
        else if (sl.includes('delay')) statusClass = 'badge-delayed';
        else if (sl.includes('process')) statusClass = 'badge-processing';

        row.innerHTML = `
            <td class="tracking-code">${trackingDisplay}</td>
            <td>${item.customer_name || item.recipient}</td>
            <td class="cell-items-detail">${details}</td>
            <td>${weight}</td>
            <td><span class="badge ${statusClass}" title="${fullStatus}">${displayStatus}</span></td>
            <td>${item.phone}</td>
            <td class="cell-address" title="${fullAddress}">${displayAddress}</td>
        `;
        tbody.appendChild(row);
    });

    document.getElementById('sh-metric-total').textContent = allShipping.length.toLocaleString();
    document.getElementById('sh-metric-recipients').textContent = recipients.size.toLocaleString();
    document.getElementById('sh-metric-weight').textContent = totalWeight.toFixed(1);
    const avg = allShipping.length > 0 ? (totalWeight / allShipping.length) : 0;
    document.getElementById('sh-metric-avg').textContent = avg.toFixed(1);
}

function filterShipments() {
    const query = (document.getElementById('sh-search')?.value || '').toLowerCase();
    const rows = document.querySelectorAll('#shipping-body tr');
    rows.forEach(row => {
        row.style.display = !query || row.textContent.toLowerCase().includes(query) ? '' : 'none';
    });
}

function exportShipments() {
    alert('Export ' + allShipping.length + ' shipments to CSV');
}

// ========== ANALYTICS PAGE ==========
function renderAnalyticsPage() {
    let totalShipped = 0, totalStockAll = 0;
    allStats.forEach(s => {
        totalShipped += (s['已发总数'] || 0);
        totalStockAll += (s['总库存'] || 0);
    });

    const totalOrders = allOrders.length + purchaseOrders.length;
    const avgPerOrder = totalOrders > 0 ? (totalShipped / totalOrders).toFixed(1) : '0';
    const turnover = totalStockAll > 0 ? (totalShipped / totalStockAll).toFixed(1) + 'x' : '0x';

    document.getElementById('an-metric-shipped').textContent = totalShipped.toLocaleString();
    document.getElementById('an-metric-orders').textContent = totalOrders.toLocaleString();
    document.getElementById('an-metric-avg').textContent = avgPerOrder;
    document.getElementById('an-metric-turnover').textContent = turnover;

    const trendShipped = totalShipped > 0 ? '+' + ((totalShipped / Math.max(totalStockAll, 1)) * 12).toFixed(1) + '%' : '—';
    const trendOrders = totalOrders > 0 ? '+' + ((totalOrders / Math.max(totalOrders - 2, 1)) * 8).toFixed(1) + '%' : '—';
    const trendAvg = '-2.1%';
    const trendTurnover = '+' + (parseFloat(turnover) > 0 ? '15.3' : '0') + '%';

    document.querySelector('#an-trend-shipped span').textContent = trendShipped;
    document.querySelector('#an-trend-orders span').textContent = trendOrders;
    document.querySelector('#an-trend-avg span').textContent = trendAvg;
    document.querySelector('#an-trend-turnover span').textContent = trendTurnover;

    // Bar Chart: Stock by Product
    renderBarChart('bar-chart', allProducts.map(p => ({
        label: p.name,
        value: p.total_stock || 0
    })), '#1e3a8a');

    // Pie Chart: Category Distribution
    let pieSigned = 0, pieUnsigned = 0, pieCn = 0;
    allProducts.forEach(p => {
        pieSigned += (p.us_signed || 0);
        pieUnsigned += (p.us_unsigned || 0);
        pieCn += (p.shipped_cn || 0);
    });
    renderPieChart([
        { label: 'US Signed (美国签收)', value: pieSigned, color: '#1e3a8a' },
        { label: 'US Unsigned (美国未签)', value: pieUnsigned, color: '#3b82f6' },
        { label: 'Shipped to CN (发往中国)', value: pieCn, color: '#60a5fa' }
    ]);

    // Shipment bar chart
    renderBarChart('shipment-bar-chart', allStats.map(s => ({
        label: s['产品名称'],
        value: s['已发总数'] || 0
    })), '#1e3a8a');

    renderSourcePerformance();
}

function renderBarChart(containerId, data, color) {
    const container = document.getElementById(containerId);
    if (!data.length) { container.innerHTML = '<p class="no-data">No data</p>'; return; }

    const maxVal = Math.max(...data.map(d => d.value), 1);
    let html = '<div class="bar-chart">';
    data.forEach(d => {
        const pct = (d.value / maxVal) * 100;
        const shortLabel = d.label.length > 10 ? d.label.substring(0, 10) + '…' : d.label;
        html += `
            <div class="bar-row">
                <div class="bar-label" title="${d.label}">${shortLabel}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:${pct}%; background:${color};"></div>
                </div>
                <div class="bar-value">${d.value}</div>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

function renderPieChart(data) {
    const total = data.reduce((sum, d) => sum + d.value, 0);
    if (total === 0) return;

    let gradParts = [];
    let cumulative = 0;
    data.forEach(d => {
        const start = (cumulative / total) * 360;
        cumulative += d.value;
        const end = (cumulative / total) * 360;
        gradParts.push(`${d.color} ${start}deg ${end}deg`);
    });

    const pieEl = document.getElementById('pie-chart');
    pieEl.style.background = `conic-gradient(${gradParts.join(', ')})`;

    const legendEl = document.getElementById('pie-legend');
    legendEl.innerHTML = data.map(d => {
        const pct = ((d.value / total) * 100).toFixed(0);
        return `<div class="legend-item">
            <span class="legend-dot" style="background:${d.color};"></span>
            <span>${d.label} <strong>${pct}%</strong></span>
        </div>`;
    }).join('');
}

function renderSourcePerformance() {
    const sourceMap = {};
    allOrders.forEach(o => {
        if (!sourceMap[o.source]) sourceMap[o.source] = { orders: 0, items: 0 };
        sourceMap[o.source].orders++;
    });

    purchaseOrders.forEach(o => {
        if (!sourceMap[o.source]) sourceMap[o.source] = { orders: 0, items: 0 };
        sourceMap[o.source].orders++;
        if (o.items) o.items.forEach(i => { sourceMap[o.source].items += Math.abs(i.qty || 0); });
    });

    const container = document.getElementById('source-performance');
    let html = '';
    Object.entries(sourceMap).forEach(([source, data]) => {
        const dotColor = source.toLowerCase().includes('stanley') ? '#1e3a8a' :
                         source.toLowerCase().includes('love') ? '#ec4899' : '#6366f1';
        html += `
            <div class="source-card">
                <div class="source-card-header">
                    <div class="source-avatar" style="background:${dotColor};"></div>
                    <div class="source-name">${source}</div>
                </div>
                <div class="source-stats">
                    <div>
                        <div class="source-stat-label">Orders</div>
                        <div class="source-stat-value">${data.orders}</div>
                    </div>
                    <div>
                        <div class="source-stat-label">Items</div>
                        <div class="source-stat-value">${data.items.toLocaleString()}</div>
                    </div>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}
