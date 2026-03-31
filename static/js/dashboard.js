/* ===================================================================
   Dashboard JS — Monitoramento Mental
   =================================================================== */

// ── Modal de edição ───────────────────────────────────────────────
function openEdit(btn) {
  var d = btn.dataset;
  document.getElementById('ed-data').value  = d.data;
  document.getElementById('ed-dor').value   = d.dor  || '';
  document.getElementById('ed-en').value    = d.en   || '';
  document.getElementById('ed-sh').value    = d.sh   || '';
  document.getElementById('ed-sq').value    = d.sq   || '';
  document.getElementById('ed-me').value    = d.me   || '';
  document.getElementById('ed-st').value    = d.st   || '';
  document.getElementById('ed-sr').value    = d.sr   || '';
  document.getElementById('ed-al').value    = d.al   || '';
  document.getElementById('ed-ci').value    = d.ci   || '';
  document.getElementById('ed-so').value    = d.so   || '';
  document.getElementById('ed-alim').value  = d.alim || '';
  document.getElementById('ed-ex').value    = d.ex   || 'Nenhum';
  document.getElementById('ed-relato').value= d.relato || '';

  // Remédios
  var arr = [];
  try { arr = JSON.parse(d.rj || '[]'); } catch(e) {}
  document.querySelectorAll('.ed-rem-qtd').forEach(function(inp) {
    var qtd = 0;
    arr.forEach(function(r) { if (r.nome === inp.dataset.nome) qtd = r.qtd || 0; });
    inp.value = qtd;
  });

  // Contextos
  var ctxArr = [];
  try { ctxArr = JSON.parse(d.ctx || '[]'); } catch(e) {}
  document.querySelectorAll('.ed-ctx-chip').forEach(function(chip) {
    chip.classList.toggle('sel', ctxArr.indexOf(chip.dataset.val) !== -1);
  });

  document.getElementById('modal').classList.add('open');
}

function closeModal() {
  document.getElementById('modal').classList.remove('open');
}

function buildRemedJson() {
  var arr = [];
  document.querySelectorAll('.ed-rem-qtd').forEach(function(inp) {
    var qtd = parseFloat(inp.value) || 0;
    arr.push({ nome: inp.dataset.nome, qtd: qtd, tomado: qtd > 0 });
  });
  document.getElementById('ed-remed-json').value = JSON.stringify(arr);
}

function buildCtxJson() {
  var arr = [];
  document.querySelectorAll('.ed-ctx-chip.sel').forEach(function(chip) {
    arr.push(chip.dataset.val);
  });
  document.getElementById('ed-ctx-json').value = JSON.stringify(arr);
}

function toggleCtxChip(btn) {
  btn.classList.toggle('sel');
}

function delDay(d) {
  if (confirm('Remover o registro de ' + d + '? Esta ação não pode ser desfeita.')) {
    document.getElementById('del-data').value = d;
    document.getElementById('form-del').submit();
  }
}

// ── Relato ────────────────────────────────────────────────────────
function mostrarFormRelato() {
  document.getElementById('relato-saved').style.display = 'none';
  document.getElementById('relato-form').style.display  = 'block';
  var raw = document.getElementById('relato-saved-raw');
  if (raw) { document.getElementById('relato-input').value = raw.dataset.raw || ''; }
}

function relatoTexto() {
  document.getElementById('relato-actions').style.display   = 'none';
  document.getElementById('relato-text-area').style.display = 'block';
}

var _rec = null, _chunks = [];

function relatoAudio() {
  document.getElementById('relato-actions').style.display    = 'none';
  document.getElementById('relato-audio-area').style.display = 'block';
}

function toggleGravacao() {
  var btn = document.getElementById('btn-rec');
  if (!_rec || _rec.state === 'inactive') {
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
      _chunks = [];
      _rec = new MediaRecorder(stream);
      _rec.ondataavailable = function(e) { if (e.data.size > 0) _chunks.push(e.data); };
      _rec.onstop = function() { document.getElementById('btn-send-audio').style.display = 'inline-block'; };
      _rec.start();
      btn.textContent = '⏹ Parar gravação';
      btn.classList.add('recording');
      document.getElementById('audio-status').textContent = 'Gravando...';
    });
  } else {
    _rec.stop();
    _rec.stream.getTracks().forEach(function(t) { t.stop(); });
    btn.textContent = '⏺ Iniciar gravação';
    btn.classList.remove('recording');
    document.getElementById('audio-status').textContent = 'Gravação concluída. Clique em Enviar.';
  }
}

function enviarRelato() {
  var texto = document.getElementById('relato-input').value.trim();
  if (!texto) return;
  var btn = document.querySelector('.relato-submit');
  btn.textContent = 'Salvando...';
  btn.disabled = true;
  var fd = new FormData();
  fd.append('texto', texto);
  fetch('/dashboard/relato', { method: 'POST', body: fd })
    .then(function(r) { return r.json().then(function(j) { return { ok: r.ok, j: j }; }); })
    .then(function(res) {
      if (res.ok && res.j.ok) { location.reload(); }
      else { btn.textContent = 'Erro: ' + (res.j.error || 'tente novamente'); btn.disabled = false; }
    })
    .catch(function() { btn.textContent = 'Erro de conexão'; btn.disabled = false; });
}

function enviarAudio() {
  var blob = new Blob(_chunks, { type: 'audio/webm' });
  var fd = new FormData();
  fd.append('audio', blob, 'relato.webm');
  document.getElementById('audio-status').textContent = 'Enviando e transcrevendo...';
  document.getElementById('btn-send-audio').disabled = true;
  fetch('/dashboard/relato-audio', { method: 'POST', body: fd })
    .then(function(r) {
      if (r.ok || r.redirected) { location.reload(); }
      else {
        document.getElementById('audio-status').textContent = 'Erro ao transcrever. Tente novamente.';
        document.getElementById('btn-send-audio').disabled = false;
      }
    })
    .catch(function() {
      document.getElementById('audio-status').textContent = 'Erro de conexão.';
      document.getElementById('btn-send-audio').disabled = false;
    });
}

// ── Relato embutido no histórico ──────────────────────────────────
function abrirRelatoEmbutido(di) {
  var form = document.getElementById('relato-' + di + '-form');
  var ta   = document.getElementById('relato-' + di + '-textarea');
  if (form) { form.style.display = form.style.display === 'none' ? 'block' : 'none'; }
  if (ta)   { ta.style.display = 'block'; }
}

function salvarRelatoEmbutido(di) {
  var inp = document.getElementById('relato-' + di + '-input');
  if (!inp) return;
  var texto = inp.value.trim();
  if (!texto) return;
  var fd = new FormData();
  fd.append('texto', texto);
  fd.append('data', di);
  fetch('/dashboard/relato', { method: 'POST', body: fd })
    .then(function(r) { return r.json().then(function(j) { return { ok: r.ok, j: j }; }); })
    .then(function(res) { if (res.ok && res.j.ok) { location.reload(); } })
    .catch(function() {});
}

// ── Remédios — Optimistic UI + Undo Toast ─────────────────────────
var _remedPending = {};  // { nome: { timer, delta, displayEl } }
var _toastTimer = null;
var _toastBarAnim = null;

function remedUpdate(nome, delta) {
  // Cancelar qualquer pendente para o mesmo remédio
  if (_remedPending[nome]) {
    clearTimeout(_remedPending[nome].timer);
    delete _remedPending[nome];
  }

  // Optimistic UI: atualizar display imediatamente
  var displayEl = document.getElementById('remed-qtd-' + nome);
  var currentVal = 0;
  if (displayEl) {
    var txt = displayEl.textContent.replace(/[^0-9.]/g, '') || '0';
    currentVal = parseFloat(txt) || 0;
  }
  var newVal = Math.max(0, currentVal + delta);
  if (displayEl) {
    displayEl.textContent = newVal > 0 ? newVal + ' comp.' : '— comp.';
  }

  // Mostrar toast undo
  _showRemedToast(nome, newVal, delta, displayEl, currentVal);

  // Agendar POST após 5s
  var t = setTimeout(function() {
    _doRemedPost(nome, delta);
    delete _remedPending[nome];
    _hideRemedToast();
  }, 5000);

  _remedPending[nome] = { timer: t, delta: delta, displayEl: displayEl, prevVal: currentVal, newVal: newVal };
}

function _doRemedPost(nome, delta) {
  var fd = new FormData();
  fd.append('nome', nome);
  fd.append('delta', delta);
  fetch('/dashboard/remed-atualizar', { method: 'POST', body: fd })
    .catch(function() {});
}

function _showRemedToast(nome, newVal, delta, displayEl, prevVal) {
  var toast = document.getElementById('remed-toast');
  if (!toast) return;

  var msg = document.getElementById('remed-toast-msg');
  if (msg) {
    var sign = delta > 0 ? '+' + delta : delta;
    msg.textContent = nome + ' → ' + (newVal > 0 ? newVal + ' comp.' : '—') + ' (' + sign + ')';
  }

  // Cancelar animação anterior
  if (_toastBarAnim) { clearInterval(_toastBarAnim); }
  var bar = document.getElementById('remed-toast-bar');
  if (bar) {
    bar.style.transition = 'none';
    bar.style.width = '100%';
    setTimeout(function() {
      bar.style.transition = 'width 5s linear';
      bar.style.width = '0%';
    }, 50);
  }

  toast.classList.add('visible');

  // Guardar para desfazer
  toast._undoNome = nome;
  toast._undoDelta = delta;
  toast._undoDisplayEl = displayEl;
  toast._undoPrevVal = prevVal;
}

function _hideRemedToast() {
  var toast = document.getElementById('remed-toast');
  if (toast) { toast.classList.remove('visible'); }
}

function desfazerRemed() {
  var toast = document.getElementById('remed-toast');
  if (!toast) return;
  var nome = toast._undoNome;
  if (!nome || !_remedPending[nome]) return;

  clearTimeout(_remedPending[nome].timer);
  var prevVal = _remedPending[nome].prevVal;
  var displayEl = _remedPending[nome].displayEl;

  // Reverter UI
  if (displayEl) {
    displayEl.textContent = prevVal > 0 ? prevVal + ' comp.' : '— comp.';
  }

  delete _remedPending[nome];
  _hideRemedToast();
}

// ── Contextos toggle ──────────────────────────────────────────────
function toggleContexto(el, label) {
  el.classList.toggle('active');
  var fd = new FormData();
  fd.append('label', label);
  fetch('/dashboard/contexto-toggle', { method: 'POST', body: fd })
    .catch(function() { el.classList.toggle('active'); });
}

// ── Alimentação ───────────────────────────────────────────────────
var _alimTimer = null;

function alimInput(v) {
  var valEl   = document.getElementById('alim-val-display');
  var lblEl   = document.getElementById('alim-label-display');
  if (valEl) valEl.textContent = v;
  if (lblEl) lblEl.textContent = alimLabel(v);
  clearTimeout(_alimTimer);
  _alimTimer = setTimeout(function() {
    var fd = new FormData();
    fd.append('valor', v);
    fetch('/dashboard/alimentacao-atualizar', { method: 'POST', body: fd });
  }, 600);
}

function alimLabel(v) {
  v = parseInt(v);
  if (v <= 1) return 'Besteira';
  if (v <= 2) return 'Ruim';
  if (v <= 3) return 'Regular';
  if (v <= 4) return 'Boa';
  return 'Saudável';
}

// ── Gráfico de tendências ─────────────────────────────────────────
(function initChart() {
  var dataEl = document.getElementById('chart-data');
  if (!dataEl) return;

  var allData30 = JSON.parse(dataEl.textContent);
  var currentRange = 7;

  var colors = {
    mental:   '#86EFAC', energia: '#FCD34D', sono:    '#A78BFA', sono_q: '#7DD3FC',
    dor:      '#FCA5A5', stress_t:'#F97316', stress_r:'#FB923C', social: '#34D399',
    rivotril: '#C084FC', zolpidem:'#67E8F9'
  };
  var names = {
    mental: 'Humor', energia: 'Energia', sono: 'Sono (h)', sono_q: 'Sono qual.',
    dor: 'Dor', stress_t: 'Stress trab.', stress_r: 'Stress rel.', social: 'Social',
    rivotril: 'Rivotril', zolpidem: 'Zolpidem'
  };
  var active = { mental: true, energia: true, sono: true };

  function sliceData(dias) {
    var n = Math.min(dias, allData30.labels.length);
    var offset = allData30.labels.length - n;
    var sliced = { labels: allData30.labels.slice(offset) };
    Object.keys(allData30).forEach(function(k) {
      if (k !== 'labels' && Array.isArray(allData30[k])) {
        sliced[k] = allData30[k].slice(offset);
      }
    });
    return sliced;
  }

  function buildDatasets(data) {
    return Object.keys(active).filter(function(k) { return active[k]; }).map(function(k) {
      return {
        label:           names[k],
        data:            data[k] || [],
        borderColor:     colors[k],
        backgroundColor: colors[k] + '33',
        borderWidth:     2,
        pointRadius:     3,
        pointHoverRadius:5,
        tension:         0.3,
        spanGaps:        true,
      };
    });
  }

  var canvasEl = document.getElementById('trend-chart');
  if (!canvasEl) return;

  var data7 = sliceData(7);
  var chart = new Chart(canvasEl.getContext('2d'), {
    type: 'line',
    data: { labels: data7.labels, datasets: buildDatasets(data7) },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { mode: 'index', intersect: false },
      },
      scales: {
        x: { ticks: { color: '#94A3B8', font: { size: 11 } }, grid: { color: '#2A2A38' } },
        y: { min: 0, ticks: { color: '#94A3B8', font: { size: 11 }, stepSize: 1 }, grid: { color: '#2A2A38' } },
      },
    },
  });

  // Range selector
  window.setRange = function(dias, btn) {
    currentRange = dias;
    document.querySelectorAll('.range-btn').forEach(function(b) { b.classList.remove('active'); });
    if (btn) btn.classList.add('active');
    var d = sliceData(dias);
    chart.data.labels = d.labels;
    chart.data.datasets = buildDatasets(d);
    chart.update();
  };

  // Toggle série
  window.toggleSerie = function(btn) {
    var serie = btn.dataset.serie;
    if (active[serie]) {
      delete active[serie];
      btn.style.background = 'var(--surface2)';
      btn.style.color      = 'var(--text3)';
    } else {
      active[serie] = true;
      btn.style.background = colors[serie] + '22';
      btn.style.color      = colors[serie];
    }
    var d = sliceData(currentRange);
    chart.data.datasets = buildDatasets(d);
    chart.update();
  };
})();
