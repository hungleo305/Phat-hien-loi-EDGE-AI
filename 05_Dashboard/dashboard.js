const $ = (id) => document.getElementById(id);
let token = sessionStorage.getItem('datnDashboardToken') || '';
let currentImage = null;
let currentImageUrl = '';
let busy = false;
let livePreviewStarted = false;
let liveImageUrl = '';
let liveFrameSequence = '';
let liveFrameTimes = [];
let lastLiveFrameAt = 0;
let nativeLive = false;
let piOffline = true;
let connectNativeLive = null;
let settingsLoaded = false;
let cameraControls = [];
let cameraEditable = false;
let lastLightReported = null;
let lastSpeedReported = null;
let wasSettingsReady = false;
let runsLoaded = false;
let selectedRun = 'current';
let selectedRunData = null;
let currentSession = null;
let activeRun = null;
let activeRunId = null;
const themeKey = 'datnDashboardTheme';
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(themeKey, theme);
  $('themeToggle').textContent = theme === 'light' ? '☾ Giao diện tối' : '☀ Giao diện sáng';
}
applyTheme(localStorage.getItem(themeKey) === 'light' ? 'light' : 'dark');
$('themeToggle').addEventListener('click', () => applyTheme(
  document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'));

function notice(message, kind = '') {
  $('notice').textContent = message;
  $('notice').className = 'notice ' + kind;
}

function timeLabel(value) {
  return value ? new Date(value * 1000).toLocaleTimeString('vi-VN', { hour12: false }) : '—';
}

function resultClass(value) {
  return value === 'PASS' ? 'pass' : value === 'DEFECT' ? 'defect' : value === 'ERROR' ? 'error' : 'neutral';
}

function displayResult(item) {
  return item.delivered ? (item.result || 'ERROR') : 'CHƯA GỬI ESP';
}

function makeCell(row, value, className = '') {
  const cell = document.createElement('td');
  cell.textContent = value;
  if (className) cell.className = className;
  row.appendChild(cell);
}

function renderHistory(items) {
  const history = $('history');
  history.replaceChildren();
  if (!items.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 4;
    cell.className = 'empty-row';
    cell.textContent = selectedRun === 'current' ? 'Chưa có kết quả.' : 'Lượt chạy này chưa có kết quả.';
    row.appendChild(cell);
    history.appendChild(row);
    return;
  }
  const visible = selectedRun === 'current' ? items.slice(0, 8) : items;
  visible.forEach(item => {
    const row = document.createElement('tr');
    makeCell(row, item.id);
    makeCell(row, displayResult(item), `history-result ${item.delivered ? resultClass(item.result) : 'error'}`);
    makeCell(row, item.total_ms != null ? `${Math.round(item.total_ms)} ms` : '—');
    makeCell(row, timeLabel(item.at));
    history.appendChild(row);
  });
}

function runLabel(run) {
  const when = run.ended_at ? new Date(run.ended_at * 1000).toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false
  }) : 'chưa có thời gian';
  return `${run.name || `Phiên ${run.session}`} · ${run.count} hộp · ${when}`;
}

async function loadSelectedRun() {
  if (selectedRun === 'current') {
    selectedRunData = null;
    return;
  }
  const data = await (await api(`/api/run/${encodeURIComponent(selectedRun)}`)).json();
  selectedRunData = data;
  renderHistory(data.results || []);
  const counts = data.counts || {};
  $('runSummary').textContent = `${data.name} · ${data.count} hộp · ${counts.PASS || 0} PASS · ${counts.DEFECT || 0} DEFECT · ${counts.ERROR || 0} ERROR`;
}

async function loadRuns() {
  try {
    const data = await (await api('/api/runs')).json();
    const previous = selectedRun;
    $('runSelect').replaceChildren();
    const current = document.createElement('option');
    current.value = 'current';
    current.textContent = activeRun ? `Đang chạy · ${activeRun.name}` : 'Chưa tạo phiên vận hành';
    $('runSelect').appendChild(current);
    for (const run of data.runs || []) {
      if (run.id === data.active_id) continue;
      const option = document.createElement('option');
      option.value = String(run.id);
      option.textContent = runLabel(run);
      $('runSelect').appendChild(option);
    }
    if ([...$('runSelect').options].some(option => option.value === previous)) {
      $('runSelect').value = previous;
    } else {
      selectedRun = 'current';
      selectedRunData = null;
    }
    await loadSelectedRun();
  } catch (error) {
    notice(`Không đọc được danh sách lượt chạy: ${error.message}`, 'bad');
  }
}

async function downloadRun(kind) {
  const runId = selectedRun === 'current' ? activeRun?.id : selectedRun;
  if (!runId) {
    notice('Chưa có phiên vận hành để xuất kết quả.', 'warn');
    return;
  }
  try {
    const response = await api(`/api/run/${encodeURIComponent(runId)}.${kind}`);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = `run_${runId}.${kind}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    notice(`Đã tạo và tải kết quả phiên ${activeRun?.id === runId ? activeRun.name : runId}.`, 'good');
  } catch (error) {
    notice(`Không thể tải kết quả: ${error.message}`, 'bad');
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: 'no-store',
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...(options.headers || {}) }
  });
  if (!response.ok) {
    let error = `HTTP ${response.status}`;
    try { error = (await response.json()).error || error; } catch (_) {}
    throw new Error(error);
  }
  return response;
}

async function showImage(path) {
  if (!path || path === currentImage) return;
  currentImage = path;
  try {
    const response = await api(path);
    const imageUrl = URL.createObjectURL(await response.blob());
    if (currentImageUrl) URL.revokeObjectURL(currentImageUrl);
    currentImageUrl = imageUrl;
    $('captureImage').src = imageUrl;
    $('captureImage').hidden = false;
    $('captureEmpty').hidden = true;
  } catch (_) { currentImage = null; }
}

function render(data) {
  const offline = !!data.offline;
  const station = data.station || {};
  const device = data.device;
  currentSession = device?.session || currentSession;
  const nextActiveRun = data.active_run || null;
  const nextActiveRunId = nextActiveRun?.id || null;
  const activeRunChanged = nextActiveRunId !== activeRunId;
  activeRun = nextActiveRun;
  activeRunId = nextActiveRunId;
  const counts = data.counts || {};
  const recent = data.recent || [];
  const total = (counts.PASS || 0) + (counts.DEFECT || 0) + (counts.ERROR || 0);
  $('totalCount').textContent = total;
  $('passCount').textContent = counts.PASS || 0;
  $('defectCount').textContent = counts.DEFECT || 0;
  $('errorCount').textContent = counts.ERROR || 0;
  $('lastUpdate').textContent = `Cập nhật ${timeLabel(data.time)}`;
  if (nativeLive) {
    const fps = Math.round(data.preview_fps || 0);
    $('liveStatus').textContent = offline ? 'Pi ngoại tuyến' : station.camera && fps
      ? `Camera trực tiếp · nguồn ${fps} FPS` : 'Đang chờ hình camera';
  }
  $('sideConnection').textContent = offline ? 'Pi ngoại tuyến' : device ? 'ESP32 đã kết nối' : 'Chờ ESP32';
  document.querySelector('.pulse').classList.toggle('on', !!device);

  const running = device && device.motor;
  const fault = !!(station.fault || (device && device.fault));
  const label = offline ? 'Pi chưa kết nối' : !device ? 'Chưa kết nối ESP32' : fault ? 'Cần kiểm tra lỗi' : running ? 'Đang chạy' : device.state === 'STOPPED' ? 'Đã dừng' : 'Đang xử lý';
  $('machineState').textContent = label;
  $('machineDetail').textContent = offline ? 'Bật nguồn Pi; trạm sẽ tự khởi động khi Pi có mạng' : device ? `ESP32: ${device.state} · Motor ${running ? 'ON' : 'OFF'}` : 'Đợi bản tin STATE từ ESP32';
  $('machineDot').className = `machine-dot ${fault ? 'fault' : running ? 'running' : ''}`;
  $('systemBadge').className = `status-badge ${offline || fault ? 'bad' : !device || !station.ai_ready ? 'muted' : ''}`;
  $('systemBadge').innerHTML = `<i></i>${offline ? 'PI NGOẠI TUYẾN' : fault ? 'CÓ LỖI' : device && station.ai_ready ? 'TRẠM SẴN SÀNG' : 'CHỜ KẾT NỐI'}`;
  $('modeBadge').textContent = device ? (device.sorting ? 'GẠT LỖI BẬT' : 'CHẠY THỬ · KHÔNG GẠT') : 'CHƯA CÓ CHẾ ĐỘ';
  $('cameraSensor').textContent = device ? (device.camera ? 'Có hộp' : 'Trống') : '—';
  $('gateSensor').textContent = device ? (device.gate ? 'Có hộp' : 'Trống') : '—';
  $('aiStatus').textContent = offline ? 'Pi ngoại tuyến' : station.fault ? 'Có lỗi' : station.busy ? 'Đang xử lý' : station.ai_ready ? 'Sẵn sàng' : 'Đang tải';
  $('queueCount').textContent = device ? `${device.queue} / 8` : '— / 8';
  $('boxId').textContent = device ? `#${device.box_id}` : '—';
  $('sessionId').textContent = device ? device.session : '—';
  const stoppedEmpty = !!(device && device.state === 'STOPPED' && !device.motor && !device.fault && !device.queue && !device.camera && !device.gate);
  const settingsReady = stoppedEmpty && !busy && !station.busy && !station.pending && !station.queue;
  if (settingsReady && !wasSettingsReady && settingsLoaded) loadSettings();
  wasSettingsReady = settingsReady;
  $('lightActual').textContent = device?.light_level ?? '—';
  $('speedActual').textContent = device?.motor_speed ?? '—';
  if (device?.light_level !== lastLightReported) {
    lastLightReported = device?.light_level ?? null;
    if (document.activeElement !== $('lightValue') && lastLightReported !== null) $('lightValue').value = lastLightReported;
  }
  if (device?.motor_speed !== lastSpeedReported) {
    lastSpeedReported = device?.motor_speed ?? null;
    if (document.activeElement !== $('speedValue') && lastSpeedReported !== null) $('speedValue').value = lastSpeedReported;
  }
  $('lightApply').disabled = !settingsReady || device?.light_level == null;
  $('speedApply').disabled = !settingsReady || device?.motor_speed == null;
  const servoReady = settingsReady && device?.servo_angle != null && !device?.servo_moving;
  const servoFields = [
    ['servoAngle', 'servoAngleActual', 'servoAngleApply', device?.servo_angle],
    ['servoSpeed', 'servoSpeedActual', 'servoSpeedApply', device?.servo_speed],
    ['servoHold', 'servoHoldActual', 'servoHoldApply', device?.servo_hold]
  ];
  for (const [input, actual, button, value] of servoFields) {
    $(actual).textContent = value ?? '—';
    $(button).disabled = !servoReady;
    if (value != null && document.activeElement !== $(input)) $(input).value = value;
  }
  $('servoNote').textContent = device?.servo_angle == null
    ? 'Cần nạp firmware ESP32 hỗ trợ cài đặt servo để chỉnh từ dashboard.'
    : `Giữ ngoài thực tế: ${device.servo_effective} ms. Tốc độ lệnh không đo lực gạt; chỉ chỉnh khi băng dừng và trống.`;
  const cameraReady = settingsReady && cameraEditable && cameraControls.length > 0;
  $('cameraField').disabled = !cameraReady;
  $('cameraValue').disabled = !cameraReady;
  $('cameraApply').disabled = !cameraReady;
  $('cameraSave').disabled = !cameraReady;
  $('cameraRestore').disabled = !cameraReady;
  $('startButton').disabled = busy || !activeRun || !(stoppedEmpty && device.ready && station.ready && station.camera && !station.busy && !station.pending && !station.queue &&
    (device.motor_speed == null || (device.motor_speed > 0 && device.light_level > 0)));
  $('stopButton').disabled = busy || !device;
  $('dryButton').disabled = busy || !stoppedEmpty;
  $('sortButton').disabled = busy || !stoppedEmpty;
  $('createRun').disabled = busy || !stoppedEmpty;
  $('dryButton').classList.toggle('selected', !!device && !device.sorting);
  $('sortButton').classList.toggle('selected', !!device && device.sorting);

  const last = recent[0];
  if (last) {
    $('lastResult').textContent = displayResult(last);
    $('lastResult').className = `result-chip ${last.delivered ? resultClass(last.result) : 'error'}`;
    $('lastReason').textContent = last.reason || 'Không có mô tả';
    $('lastLatency').textContent = last.total_ms != null ? `${Math.round(last.total_ms)} ms` : '—';
    $('captureTime').textContent = timeLabel(last.at);
    showImage(last.image);
  } else {
    currentImage = null;
    if (currentImageUrl) URL.revokeObjectURL(currentImageUrl);
    currentImageUrl = '';
    $('captureImage').hidden = true;
    $('captureEmpty').hidden = false;
    $('lastResult').textContent = 'CHƯA CÓ KẾT QUẢ';
    $('lastResult').className = 'result-chip neutral';
    $('lastReason').textContent = offline ? 'Pi ngoại tuyến' : 'Đang chờ hộp đầu tiên';
    $('lastLatency').textContent = '—';
    $('captureTime').textContent = '—';
  }
  renderHistory(selectedRunData ? selectedRunData.results || [] : recent);
  if (selectedRun === 'current') {
    $('runSummary').textContent = activeRun
      ? `${activeRun.name} · ${total} hộp · ${counts.PASS || 0} PASS · ${counts.DEFECT || 0} DEFECT · ${counts.ERROR || 0} ERROR`
      : 'Chưa tạo phiên vận hành · nhập tên phiên mới khi băng đã dừng và trống';
  }
  $('downloadCsv').disabled = !activeRun && selectedRun === 'current';
  $('downloadJson').disabled = !activeRun && selectedRun === 'current';
  if (activeRunChanged && runsLoaded) loadRuns();
  const operation = [...(data.operations || [])].reverse()[0];
  if (offline) {
    notice('Pi đang tắt hoặc chưa kết nối mạng. Dashboard sẽ tự nối và mở trạm khi Pi sẵn sàng.', 'bad');
  } else if (operation && Date.now() / 1000 - operation.updated < 8) {
    const names = { START: 'Chạy', STOP: 'Dừng', DRY: 'Không gạt', SORT: 'Gạt lỗi', SPEED: 'Tốc độ', LIGHT: 'Đèn', SERVO_ANGLE: 'Góc gạt', SERVO_SPEED: 'Tốc độ gạt', SERVO_HOLD: 'Giữ ngoài' };
    const states = { queued: 'đang chờ gửi', sent: 'đã gửi tới ESP32', accepted: 'ESP32 đã chấp nhận', denied: 'ESP32 từ chối', timeout: 'chưa nhận xác nhận', cancelled: 'đã hủy do trạng thái thay đổi' };
    notice(`${names[operation.verb]}: ${states[operation.state] || operation.state}`, operation.state === 'accepted' ? 'good' : ['denied', 'timeout', 'cancelled'].includes(operation.state) ? 'bad' : '');
  } else if (fault) {
    notice(station.fault || 'ESP32 đang báo lỗi. Dừng và kiểm tra băng tải.', 'bad');
  } else {
    notice('Trạng thái được cập nhật trực tiếp từ trạm Pi và ESP32.', 'good');
  }
}

async function refresh() {
  try {
    const data = await (await api('/api/state')).json();
    $('login').hidden = true;
    $('content').hidden = false;
    startLivePreview(data.local_trust);
    piOffline = !!data.offline;
    if (piOffline) {
      settingsLoaded = false;
      cameraEditable = false;
      cameraControls = [];
      wasSettingsReady = false;
    } else if (!settingsLoaded) {
      settingsLoaded = true;
      loadSettings();
    }
    if (nativeLive && connectNativeLive) {
      if (piOffline) connectNativeLive(false);
      else if (!document.hidden && !$('liveImage').dataset.streaming) connectNativeLive(true);
    }
    render(data);
    if (!runsLoaded) {
      runsLoaded = true;
      loadRuns();
    }
  } catch (error) {
    if (error.message === 'Unauthorized') {
      token = '';
      sessionStorage.removeItem('datnDashboardToken');
      $('login').hidden = false;
      $('content').hidden = true;
      notice('Mã truy cập không đúng.', 'bad');
    } else notice(`Mất kết nối dashboard: ${error.message}`, 'bad');
  }
}

function selectedCameraControl() {
  return cameraControls.find(control => control.name === $('cameraField').value);
}

function renderCameraSelection() {
  const control = selectedCameraControl();
  if (!control) return;
  $('cameraValue').min = control.min;
  $('cameraValue').max = control.max;
  $('cameraValue').step = control.step;
  $('cameraValue').value = control.value;
  $('cameraActual').textContent = control.value;
  $('cameraSaved').textContent = control.saved ?? 'chưa lưu';
  $('cameraRange').textContent = `${control.min}…${control.max}, bước ${control.step}`;
}

async function loadSettings() {
  try {
    const data = await (await api('/api/settings')).json();
    cameraControls = data.camera || [];
    cameraEditable = !!data.editable;
    const previous = $('cameraField').value;
    $('cameraField').replaceChildren();
    for (const control of cameraControls) {
      const option = document.createElement('option');
      option.value = control.name;
      option.textContent = control.label;
      $('cameraField').appendChild(option);
    }
    if (cameraControls.some(control => control.name === previous)) $('cameraField').value = previous;
    renderCameraSelection();
    $('cameraProfileNote').textContent = data.camera_saved
      ? `Cấu hình camera khởi động đã lưu${data.camera_saved_at ? ' lúc ' + new Date(data.camera_saved_at).toLocaleString('vi-VN') : ''}. Mỗi thông số hiển thị giá trị hiện tại và giá trị được áp dụng khi mở trạm.`
      : 'Chưa có cấu hình camera khởi động.';
    $('cameraSettingNote').textContent = data.camera_error || (cameraControls.length
      ? 'Áp dụng thử chỉ đổi camera hiện tại. Xem ảnh live và kết quả trước khi lưu.'
      : 'Camera chưa trả danh sách thông số có thể chỉnh.');
  } catch (error) {
    settingsLoaded = false;
    $('cameraSettingNote').textContent = `Không đọc được camera: ${error.message}`;
  }
}

async function postSetting(payload) {
  busy = true;
  try {
    const response = await api('/api/settings', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const result = await response.json();
    if (result.sequence) notice(`Đã gửi ${payload.target} (#${result.sequence}); chờ ESP32 xác nhận.`);
    else notice('Đã áp dụng cài đặt camera.', 'good');
    if (payload.target.startsWith('CAMERA_')) await loadSettings();
  } catch (error) { notice(error.message, 'bad'); }
  finally { busy = false; refresh(); }
}

$('cameraField').addEventListener('change', renderCameraSelection);
$('cameraRefresh').addEventListener('click', loadSettings);
$('lightApply').addEventListener('click', () => {
  if ($('lightValue').value && $('lightValue').checkValidity())
    postSetting({ target: 'LIGHT', value: Number($('lightValue').value) });
  else notice('Giá trị đèn phải từ 0 đến 255.', 'bad');
});
$('speedApply').addEventListener('click', () => {
  if ($('speedValue').value && $('speedValue').checkValidity())
    postSetting({ target: 'SPEED', value: Number($('speedValue').value) });
  else notice('PWM băng tải phải từ 1 đến 255.', 'bad');
});
for (const [input, button, target] of [
  ['servoAngle', 'servoAngleApply', 'SERVO_ANGLE'],
  ['servoSpeed', 'servoSpeedApply', 'SERVO_SPEED'],
  ['servoHold', 'servoHoldApply', 'SERVO_HOLD']
]) {
  $(button).addEventListener('click', () => {
    if ($(input).value && $(input).checkValidity())
      postSetting({ target, value: Number($(input).value) });
    else notice('Giá trị servo ngoài phạm vi cho phép.', 'bad');
  });
}
$('cameraApply').addEventListener('click', () => {
  if ($('cameraValue').value && $('cameraValue').checkValidity())
    postSetting({ target: 'CAMERA_APPLY', name: $('cameraField').value,
      value: Number($('cameraValue').value) });
  else notice('Giá trị camera nằm ngoài phạm vi thiết bị.', 'bad');
});
$('cameraSave').addEventListener('click', () => {
  if (confirm('Lưu thông số camera hiện tại để dùng ở lần khởi động sau?')) postSetting({ target: 'CAMERA_SAVE' });
});
$('cameraRestore').addEventListener('click', () => {
  if (confirm('Khôi phục profile camera gốc trước lần lưu đầu tiên qua dashboard?')) postSetting({ target: 'CAMERA_RESTORE' });
});

function startLivePreview(localTrust) {
  if (livePreviewStarted) return;
  livePreviewStarted = true;
  if (localTrust) {
    nativeLive = true;
    const live = $('liveImage');
    live.onload = () => {
      live.hidden = false;
      $('liveEmpty').hidden = true;
    };
    live.onerror = () => {
      live.hidden = true;
      $('liveEmpty').hidden = false;
      live.dataset.streaming = '';
      live.removeAttribute('src');
      $('liveStatus').textContent = piOffline ? 'Pi ngoại tuyến' : 'Đang chờ hình camera';
    };
    connectNativeLive = (enabled) => {
      if (!enabled) {
        live.removeAttribute('src');
        live.dataset.streaming = '';
        live.hidden = true;
        $('liveEmpty').hidden = false;
      } else {
        live.src = `/api/live.mjpg?t=${Date.now()}`;
        live.dataset.streaming = '1';
        live.hidden = false;
        $('liveEmpty').hidden = true;
      }
    };
    document.addEventListener('visibilitychange', () => connectNativeLive(!document.hidden && !piOffline));
    return;
  }
  updateLivePreview();
  updateLivePreview();
}

async function updateLivePreview() {
  let delay = 0;
  if (!$('content').hidden && !document.hidden) {
    try {
      const response = await api('/api/live.jpg', {
        headers: { 'X-Last-Frame': liveFrameSequence || '0' }
      });
      const sequence = response.headers.get('X-Frame-Sequence') || '';
      const imageBlob = await response.blob();
      if (Number(sequence) > Number(liveFrameSequence)) {
        const nextUrl = URL.createObjectURL(imageBlob);
        $('liveImage').src = nextUrl;
        $('liveImage').hidden = false;
        $('liveEmpty').hidden = true;
        if (liveImageUrl) URL.revokeObjectURL(liveImageUrl);
        liveImageUrl = nextUrl;
        liveFrameSequence = sequence;
        const now = performance.now();
        lastLiveFrameAt = now;
        liveFrameTimes.push(now);
        liveFrameTimes = liveFrameTimes.filter(at => now - at <= 2000);
        const fps = liveFrameTimes.length > 1
          ? Math.round(1000 * (liveFrameTimes.length - 1) / (now - liveFrameTimes[0])) : 0;
        $('liveStatus').textContent = fps ? `Camera trực tiếp · ${fps} FPS` : 'Camera trực tiếp';
      }
    } catch (error) {
      if (performance.now() - lastLiveFrameAt > 1500) {
        $('liveImage').hidden = true;
        $('liveEmpty').hidden = false;
        $('liveStatus').textContent = 'Đang chờ hình camera';
        liveFrameSequence = '';
        liveFrameTimes = [];
      }
      delay = 400;
    }
  } else {
    delay = 500;
  }
  setTimeout(updateLivePreview, delay);
}

$('loginForm').addEventListener('submit', event => {
  event.preventDefault();
  token = $('token').value.trim();
  sessionStorage.setItem('datnDashboardToken', token);
  $('token').value = '';
  refresh();
});

document.querySelectorAll('[data-command]').forEach(button => button.addEventListener('click', async () => {
  const command = button.dataset.command;
  if (command === 'START' && !confirm('Đã lấy hết hộp khỏi băng tải và kiểm tra vùng nguy hiểm? Bắt đầu chạy băng tải?')) return;
  if (command === 'SORT' && !confirm('Bật gạt lỗi thật? Kiểm tra góc servo và máng lỗi trước khi tiếp tục.')) return;
  busy = true;
  button.disabled = true;
  try {
    const response = await api('/api/command', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ command }) });
    const result = await response.json();
    notice(`Đã xếp lệnh ${command} (#${result.sequence}); chờ ESP32 xác nhận.`);
  } catch (error) { notice(error.message, 'bad'); }
  busy = false;
  refresh();
}));

$('runSelect').addEventListener('change', async event => {
  selectedRun = event.target.value;
  selectedRunData = null;
  try {
    await loadSelectedRun();
    refresh();
  } catch (error) {
    notice(`Không đọc được lượt chạy: ${error.message}`, 'bad');
  }
});

$('createRun').addEventListener('click', async () => {
  const name = $('runName').value.trim();
  if (!name) {
    notice('Nhập tên phiên trước khi tạo.', 'warn');
    $('runName').focus();
    return;
  }
  if (!confirm(`Tạo phiên mới “${name}”? Lịch sử trên màn hình sẽ bắt đầu lại từ 0; dữ liệu phiên cũ vẫn được giữ để xem và tải.`)) return;
  busy = true;
  $('createRun').disabled = true;
  try {
    const response = await api('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    const result = await response.json();
    activeRun = result.run;
    activeRunId = result.run.id;
    selectedRun = 'current';
    selectedRunData = null;
    $('runName').value = '';
    await loadRuns();
    notice(`Đã tạo phiên “${result.run.name}”. Bộ đếm và lịch sử hiện tại đã làm mới.`, 'good');
  } catch (error) {
    notice(`Không thể tạo phiên: ${error.message}`, 'bad');
  } finally {
    busy = false;
    refresh();
  }
});

$('runName').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !$('createRun').disabled) $('createRun').click();
});

$('runRefresh').addEventListener('click', loadRuns);
$('downloadCsv').addEventListener('click', () => downloadRun('csv'));
$('downloadJson').addEventListener('click', () => downloadRun('json'));

setInterval(() => { $('clock').textContent = new Date().toLocaleString('vi-VN', { hour12: false }); }, 1000);
setInterval(refresh, 1500);
refresh();


// === POP-UP MODAL CONTROLLER ===
const settingsModal = $('settingsModal');
function openSettingsModal() {
  if (!settingsModal) return;
  settingsModal.hidden = false;
  document.body.style.overflow = 'hidden';
}
function closeSettingsModal() {
  if (!settingsModal) return;
  settingsModal.hidden = true;
  document.body.style.overflow = '';
}
$('openSettingsTop')?.addEventListener('click', openSettingsModal);
$('openSettingsNav')?.addEventListener('click', (e) => {
  e.preventDefault();
  openSettingsModal();
});
$('settingsCloseBtn')?.addEventListener('click', closeSettingsModal);
settingsModal?.addEventListener('click', (e) => {
  if (e.target === settingsModal) closeSettingsModal();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && settingsModal && !settingsModal.hidden) {
    closeSettingsModal();
  }
});
