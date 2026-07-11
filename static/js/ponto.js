(() => {
    const video = document.getElementById('camera');
    if (!video) return;

    const canvas = document.getElementById('captura');
    const preview = document.getElementById('fotoPreview');
    const placeholder = document.getElementById('cameraPlaceholder');
    const btnCamera = document.getElementById('btnCamera');
    const btnFoto = document.getElementById('btnFoto');
    const btnLocal = document.getElementById('btnLocal');
    const locationStatus = document.getElementById('locationStatus');
    const syncStatus = document.getElementById('syncStatus');
    const colaboradorId = document.getElementById('colaboradorId').value;

    let stream = null;
    let fotoBlob = null;
    let localizacao = null;

    function agoraLocal() {
        return new Date();
    }

    function atualizarRelogio() {
        const el = document.getElementById('relogio');
        if (el) el.textContent = agoraLocal().toLocaleTimeString('pt-BR');
    }
    atualizarRelogio();
    setInterval(atualizarRelogio, 1000);

    function getDeviceId() {
        let id = localStorage.getItem('msm_device_id');
        if (!id) {
            id = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
            localStorage.setItem('msm_device_id', id);
        }
        return id;
    }

    async function ativarCamera() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
                audio: false,
            });
            video.srcObject = stream;
            video.style.display = 'block';
            placeholder.style.display = 'none';
            preview.style.display = 'none';
            btnFoto.disabled = false;
            syncStatus.innerHTML = '<div class="alert alert-success py-2">Câmera pronta.</div>';
        } catch (erro) {
            syncStatus.innerHTML = '<div class="alert alert-danger py-2">Não foi possível acessar a câmera. Verifique a permissão do navegador.</div>';
        }
    }

    function capturarFoto() {
        if (!stream) return;
        const largura = video.videoWidth || 720;
        const altura = video.videoHeight || 720;
        canvas.width = largura;
        canvas.height = altura;
        canvas.getContext('2d').drawImage(video, 0, 0, largura, altura);
        canvas.toBlob((blob) => {
            fotoBlob = blob;
            preview.src = URL.createObjectURL(blob);
            preview.style.display = 'block';
            video.style.display = 'none';
            placeholder.style.display = 'none';
            syncStatus.innerHTML = '<div class="alert alert-success py-2">Foto facial capturada.</div>';
        }, 'image/jpeg', 0.88);
    }

    function obterLocalizacao() {
        if (!navigator.geolocation) {
            locationStatus.innerHTML = '<i class="bi bi-exclamation-triangle"></i> GPS indisponível neste aparelho.';
            return;
        }
        locationStatus.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Obtendo localização...';
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                localizacao = {
                    latitude: pos.coords.latitude,
                    longitude: pos.coords.longitude,
                    precisao: pos.coords.accuracy,
                };
                locationStatus.innerHTML = `<i class="bi bi-geo-alt-fill text-success"></i> Localização obtida · precisão aproximada de ${Math.round(pos.coords.accuracy)} m`;
            },
            () => {
                locationStatus.innerHTML = '<i class="bi bi-exclamation-triangle text-warning"></i> Não foi possível obter o GPS. O ponto ainda poderá ser enviado, mas ficará sem validação de local.';
            },
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 }
        );
    }

    function filaOffline() {
        try { return JSON.parse(localStorage.getItem('msm_ponto_offline') || '[]'); }
        catch { return []; }
    }

    function salvarFila(item) {
        const fila = filaOffline();
        fila.push(item);
        localStorage.setItem('msm_ponto_offline', JSON.stringify(fila));
    }

    async function blobParaBase64(blob) {
        return await new Promise((resolve) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.readAsDataURL(blob);
        });
    }

    function base64ParaBlob(dataUrl) {
        const [cabecalho, dados] = dataUrl.split(',');
        const mime = cabecalho.match(/:(.*?);/)[1];
        const binario = atob(dados);
        const bytes = new Uint8Array(binario.length);
        for (let i = 0; i < binario.length; i += 1) bytes[i] = binario.charCodeAt(i);
        return new Blob([bytes], { type: mime });
    }

    async function enviarRegistro(registro, foto) {
        const form = new FormData();
        Object.entries(registro).forEach(([chave, valor]) => {
            if (valor !== null && valor !== undefined) form.append(chave, valor);
        });
        form.append('foto', foto, 'ponto.jpg');
        const resposta = await fetch('/api/ponto/registrar', { method: 'POST', body: form });
        const dados = await resposta.json();
        if (!resposta.ok || !dados.ok) throw new Error(dados.erro || 'Falha ao registrar ponto.');
        return dados;
    }

    async function registrar(tipo) {
        if (!fotoBlob) {
            syncStatus.innerHTML = '<div class="alert alert-warning py-2">Capture a foto facial antes de registrar.</div>';
            return;
        }

        const registro = {
            client_uuid: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
            colaborador_id: colaboradorId,
            tipo,
            capturado_em: agoraLocal().toISOString(),
            latitude: localizacao?.latitude,
            longitude: localizacao?.longitude,
            precisao_metros: localizacao?.precisao,
            dispositivo_id: getDeviceId(),
            dispositivo_info: navigator.userAgent,
        };

        syncStatus.innerHTML = '<div class="alert alert-info py-2"><span class="spinner-border spinner-border-sm"></span> Registrando ponto...</div>';

        if (!navigator.onLine) {
            salvarFila({ registro, fotoBase64: await blobParaBase64(fotoBlob) });
            syncStatus.innerHTML = '<div class="alert alert-warning py-2"><i class="bi bi-cloud-slash"></i> Sem internet. O ponto foi guardado neste aparelho e será sincronizado automaticamente.</div>';
            return;
        }

        try {
            const dados = await enviarRegistro(registro, fotoBlob);
            const area = dados.dentro_geocerca === true ? ' · dentro da área' : dados.dentro_geocerca === false ? ' · fora da área' : '';
            syncStatus.innerHTML = `<div class="alert alert-success"><strong>Ponto registrado!</strong><br>${dados.tipo}${area}</div>`;
            setTimeout(() => window.location.reload(), 1200);
        } catch (erro) {
            salvarFila({ registro, fotoBase64: await blobParaBase64(fotoBlob) });
            syncStatus.innerHTML = `<div class="alert alert-warning py-2">Não foi possível enviar agora. O registro ficou salvo para sincronização. ${erro.message}</div>`;
        }
    }

    async function sincronizarFila() {
        if (!navigator.onLine) return;
        const fila = filaOffline();
        if (!fila.length) return;
        const restantes = [];
        for (const item of fila) {
            try {
                await enviarRegistro(item.registro, base64ParaBlob(item.fotoBase64));
            } catch {
                restantes.push(item);
            }
        }
        localStorage.setItem('msm_ponto_offline', JSON.stringify(restantes));
        if (!restantes.length) {
            syncStatus.innerHTML = '<div class="alert alert-success py-2"><i class="bi bi-cloud-check"></i> Marcações offline sincronizadas.</div>';
            setTimeout(() => window.location.reload(), 1200);
        }
    }

    btnCamera.addEventListener('click', ativarCamera);
    btnFoto.addEventListener('click', capturarFoto);
    btnLocal.addEventListener('click', obterLocalizacao);
    document.querySelectorAll('.ponto-action').forEach((botao) => {
        botao.addEventListener('click', () => registrar(botao.dataset.tipo));
    });
    window.addEventListener('online', sincronizarFila);
    sincronizarFila();
})();
