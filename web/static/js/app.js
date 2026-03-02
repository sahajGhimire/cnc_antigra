/**
 * CNC Operating System — Frontend Application
 * Handles mode switching, API calls, voice recording, SVG preview, and GRBL streaming.
 */

(function () {
    'use strict';

    // ================================================================
    // State
    // ================================================================
    let currentTab = 'write';
    let currentSvg = '';
    let currentGcode = '';
    let selectedShape = 'circle';
    let uploadedFile = null;
    let isRecording = false;
    let mediaRecorder = null;
    let audioChunks = [];

    // ================================================================
    // DOM References
    // ================================================================
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // Tabs
    const tabBtns = $$('.tab-btn');
    const panels = {
        write: $('#panel-write'),
        draw: $('#panel-draw'),
        image: $('#panel-image'),
    };

    // Output
    const previewViewport = $('#preview-viewport');
    const gcodeOutput = $('#gcode-output');
    const warningsCard = $('#warnings-card');
    const warningsList = $('#warnings-list');

    // Buttons
    const btnGenerateWrite = $('#btn-generate-write');
    const btnGenerateDraw = $('#btn-generate-draw');
    const btnGenerateImage = $('#btn-generate-image');
    const btnCopyGcode = $('#btn-copy-gcode');
    const btnDownloadGcode = $('#btn-download-gcode');
    const btnDownloadSvg = $('#btn-download-svg');
    const btnStreamGcode = $('#btn-stream-gcode');

    // Connection
    const btnConnect = $('#btn-connect');
    const connectModal = $('#connect-modal');
    const modalClose = $('#modal-close');
    const btnDoConnect = $('#btn-do-connect');
    const btnDoDisconnect = $('#btn-do-disconnect');
    const btnRefreshPorts = $('#btn-refresh-ports');
    const serialPortSelect = $('#serial-port');
    const modalStatus = $('#modal-status');
    const connectionStatus = $('#connection-status');

    // Loading
    const loadingOverlay = $('#loading-overlay');
    const loadingText = $('#loading-text');

    // Voice
    const btnMicWrite = $('#btn-mic-write');

    // Image upload
    const uploadZone = $('#upload-zone');
    const imageInput = $('#image-input');

    // Shape picker
    const shapeBtns = $$('.shape-btn');

    // ================================================================
    // Tab Switching
    // ================================================================
    tabBtns.forEach((btn) => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            if (tab === currentTab) return;
            currentTab = tab;

            tabBtns.forEach((b) => b.classList.remove('active'));
            btn.classList.add('active');

            Object.entries(panels).forEach(([key, panel]) => {
                panel.classList.toggle('hidden', key !== tab);
            });
        });
    });

    // ================================================================
    // Shape Picker
    // ================================================================
    shapeBtns.forEach((btn) => {
        btn.addEventListener('click', () => {
            shapeBtns.forEach((b) => b.classList.remove('active'));
            btn.classList.add('active');
            selectedShape = btn.dataset.shape;

            // Toggle extra params
            const sidesGroup = $('#param-sides-group');
            const pointsGroup = $('#param-points-group');
            sidesGroup.classList.toggle('hidden', selectedShape !== 'polygon');
            pointsGroup.classList.toggle('hidden', selectedShape !== 'star');
        });
    });

    // ================================================================
    // API Helpers
    // ================================================================
    async function apiPost(url, data, isFormData = false) {
        showLoading('Generating...');
        try {
            const opts = { method: 'POST' };
            if (isFormData) {
                opts.body = data;
            } else {
                opts.headers = { 'Content-Type': 'application/json' };
                opts.body = JSON.stringify(data);
            }
            const resp = await fetch(url, opts);
            if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
            return await resp.json();
        } catch (err) {
            showWarnings([`Error: ${err.message}`]);
            return null;
        } finally {
            hideLoading();
        }
    }

    async function apiGet(url) {
        const resp = await fetch(url);
        return resp.json();
    }

    // ================================================================
    // Render Output
    // ================================================================
    function renderOutput(result) {
        if (!result) return;

        // SVG preview
        if (result.svg) {
            currentSvg = result.svg;
            previewViewport.innerHTML = result.svg;
            btnDownloadSvg.disabled = false;

            // Style embedded SVG for dark theme
            const svgEl = previewViewport.querySelector('svg');
            if (svgEl) {
                svgEl.style.maxWidth = '100%';
                svgEl.style.maxHeight = '100%';
                // Change stroke color for visibility on dark bg
                const g = svgEl.querySelector('g');
                if (g) g.setAttribute('stroke', '#63b3ed');
            }
        } else {
            previewViewport.innerHTML = '<div class="preview-empty"><p>No preview generated</p></div>';
            btnDownloadSvg.disabled = true;
        }

        // G-code
        if (result.gcode) {
            currentGcode = result.gcode;
            gcodeOutput.innerHTML = `<code>${escapeHtml(result.gcode)}</code>`;
            btnCopyGcode.disabled = false;
            btnDownloadGcode.disabled = false;
            btnStreamGcode.disabled = false;
        } else {
            gcodeOutput.innerHTML = '<code>; No G-code generated</code>';
            btnCopyGcode.disabled = true;
            btnDownloadGcode.disabled = true;
            btnStreamGcode.disabled = true;
        }

        // Warnings
        showWarnings(result.warnings || []);
    }

    function showWarnings(warnings) {
        if (warnings.length > 0) {
            warningsCard.classList.remove('hidden');
            warningsList.innerHTML = warnings
                .map((w) => `<li>${escapeHtml(w)}</li>`)
                .join('');
        } else {
            warningsCard.classList.add('hidden');
        }
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ================================================================
    // Writing Mode
    // ================================================================
    btnGenerateWrite.addEventListener('click', async () => {
        const text = $('#write-text').value;
        if (!text.trim()) {
            showWarnings(['Please enter some text']);
            return;
        }

        const result = await apiPost('/api/write', {
            text: text,
            font_size: parseFloat($('#write-fontsize').value) || 10,
            x: parseFloat($('#write-x').value) || 10,
            y: parseFloat($('#write-y').value) || 10,
            feed_rate: parseFloat($('#write-feed').value) || 800,
        });
        renderOutput(result);
    });

    // ================================================================
    // Drawing Mode
    // ================================================================
    btnGenerateDraw.addEventListener('click', async () => {
        const params = {
            size: parseFloat($('#draw-size').value) || 50,
            cx: parseFloat($('#draw-cx').value) || 150,
            cy: parseFloat($('#draw-cy').value) || 200,
        };

        if (selectedShape === 'polygon') {
            params.sides = parseInt($('#draw-sides').value) || 6;
        }
        if (selectedShape === 'star') {
            params.points = parseInt($('#draw-points').value) || 5;
        }

        const result = await apiPost('/api/draw', {
            shape: selectedShape,
            params: params,
        });
        renderOutput(result);
    });

    // ================================================================
    // Image Mode
    // ================================================================
    uploadZone.addEventListener('click', () => imageInput.click());
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleImageFile(e.dataTransfer.files[0]);
        }
    });

    imageInput.addEventListener('change', () => {
        if (imageInput.files.length) {
            handleImageFile(imageInput.files[0]);
        }
    });

    function handleImageFile(file) {
        uploadedFile = file;
        uploadZone.classList.add('has-file');
        uploadZone.querySelector('p').textContent = file.name;
        uploadZone.querySelector('.hint').textContent =
            `${(file.size / 1024).toFixed(1)} KB`;
        btnGenerateImage.disabled = false;
    }

    btnGenerateImage.addEventListener('click', async () => {
        if (!uploadedFile) return;

        const formData = new FormData();
        formData.append('image', uploadedFile);
        formData.append('threshold', $('#img-threshold').value);
        formData.append('epsilon', $('#img-epsilon').value);
        formData.append('invert', $('#img-invert').checked ? 'true' : 'false');

        const result = await apiPost('/api/image', formData, true);
        renderOutput(result);
    });

    // ================================================================
    // Voice Input (Web Speech API + Whisper fallback)
    // ================================================================
    btnMicWrite.addEventListener('click', () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    function startRecording() {
        // Try Web Speech API first
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition =
                window.SpeechRecognition || window.webkitSpeechRecognition;
            const recognition = new SpeechRecognition();
            recognition.lang = 'en-US';
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;

            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                $('#write-text').value += transcript;
                stopRecordingUI();
            };

            recognition.onerror = () => {
                // Fallback to MediaRecorder + Whisper
                startMediaRecording();
            };

            recognition.onend = () => {
                stopRecordingUI();
            };

            recognition.start();
            isRecording = true;
            btnMicWrite.classList.add('recording');
        } else {
            startMediaRecording();
        }
    }

    function startMediaRecording() {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then((stream) => {
                audioChunks = [];
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
                mediaRecorder.onstop = async () => {
                    stream.getTracks().forEach((t) => t.stop());
                    const blob = new Blob(audioChunks, { type: 'audio/webm' });
                    const formData = new FormData();
                    formData.append('audio', blob, 'recording.webm');

                    showLoading('Transcribing...');
                    try {
                        const resp = await fetch('/api/voice', {
                            method: 'POST',
                            body: formData,
                        });
                        const result = await resp.json();
                        if (result.text) {
                            $('#write-text').value += result.text;
                        }
                        if (result.error) {
                            showWarnings([result.error]);
                        }
                    } catch (err) {
                        showWarnings([`Voice error: ${err.message}`]);
                    }
                    hideLoading();
                };
                mediaRecorder.start();
                isRecording = true;
                btnMicWrite.classList.add('recording');
            })
            .catch((err) => {
                showWarnings([`Microphone access denied: ${err.message}`]);
            });
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
        }
        stopRecordingUI();
    }

    function stopRecordingUI() {
        isRecording = false;
        btnMicWrite.classList.remove('recording');
    }

    // ================================================================
    // Output Actions
    // ================================================================
    btnCopyGcode.addEventListener('click', () => {
        navigator.clipboard.writeText(currentGcode).then(() => {
            const orig = btnCopyGcode.innerHTML;
            btnCopyGcode.innerHTML = '<span>✓ Copied</span>';
            setTimeout(() => (btnCopyGcode.innerHTML = orig), 1500);
        });
    });

    btnDownloadGcode.addEventListener('click', () => {
        downloadFile(currentGcode, 'output.gcode', 'text/plain');
    });

    btnDownloadSvg.addEventListener('click', () => {
        downloadFile(currentSvg, 'preview.svg', 'image/svg+xml');
    });

    function downloadFile(content, filename, mime) {
        const blob = new Blob([content], { type: mime });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    // ================================================================
    // GRBL Connection Modal
    // ================================================================
    btnConnect.addEventListener('click', () => {
        connectModal.classList.remove('hidden');
        refreshPorts();
    });

    modalClose.addEventListener('click', () => {
        connectModal.classList.add('hidden');
    });

    connectModal.addEventListener('click', (e) => {
        if (e.target === connectModal) connectModal.classList.add('hidden');
    });

    btnRefreshPorts.addEventListener('click', refreshPorts);

    async function refreshPorts() {
        const ports = await apiGet('/api/stream/ports');
        serialPortSelect.innerHTML = '';
        if (ports && ports.length > 0) {
            ports.forEach((p) => {
                const opt = document.createElement('option');
                opt.value = p.port;
                opt.textContent = `${p.port} — ${p.description}`;
                serialPortSelect.appendChild(opt);
            });
        } else {
            const opt = document.createElement('option');
            opt.value = 'COM3';
            opt.textContent = 'COM3 (default)';
            serialPortSelect.appendChild(opt);
        }
    }

    btnDoConnect.addEventListener('click', async () => {
        const port = serialPortSelect.value;
        modalStatus.textContent = 'Connecting...';
        const result = await apiPost('/api/stream/connect', { port });
        if (result && result.success) {
            modalStatus.textContent = `✓ ${result.message} — ${result.version || ''}`;
            setConnected(true);
            btnDoConnect.disabled = true;
            btnDoDisconnect.disabled = false;
        } else {
            modalStatus.textContent = `✗ ${result ? result.message : 'Failed'}`;
        }
    });

    btnDoDisconnect.addEventListener('click', async () => {
        await apiPost('/api/stream/disconnect', {});
        modalStatus.textContent = 'Disconnected';
        setConnected(false);
        btnDoConnect.disabled = false;
        btnDoDisconnect.disabled = true;
    });

    function setConnected(connected) {
        const dot = connectionStatus.querySelector('.status-dot');
        const text = connectionStatus.querySelector('.status-text');
        dot.className = 'status-dot ' + (connected ? 'connected' : 'disconnected');
        text.textContent = connected ? 'Connected' : 'Disconnected';
    }

    // ================================================================
    // Stream G-code to Machine
    // ================================================================
    btnStreamGcode.addEventListener('click', async () => {
        if (!currentGcode) return;

        const confirmed = confirm(
            'Send G-code to CNC machine?\n\nMake sure the machine is connected and ready.'
        );
        if (!confirmed) return;

        showLoading('Streaming to machine...');
        const result = await apiPost('/api/stream/send', { gcode: currentGcode });
        hideLoading();

        if (result) {
            const msgs = [];
            if (result.success) {
                msgs.push(`✓ Sent ${result.lines_sent} lines successfully`);
            } else {
                msgs.push(`✗ Streaming failed`);
            }
            if (result.errors && result.errors.length) {
                msgs.push(...result.errors);
            }
            showWarnings(msgs);
        }
    });

    // ================================================================
    // Loading Overlay
    // ================================================================
    function showLoading(msg) {
        loadingText.textContent = msg || 'Processing...';
        loadingOverlay.classList.remove('hidden');
    }

    function hideLoading() {
        loadingOverlay.classList.add('hidden');
    }

    // ================================================================
    // Keyboard shortcuts
    // ================================================================
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            if (currentTab === 'write') btnGenerateWrite.click();
            else if (currentTab === 'draw') btnGenerateDraw.click();
            else if (currentTab === 'image') btnGenerateImage.click();
        }
    });

})();
