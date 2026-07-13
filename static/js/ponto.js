(() => {
    const video = document.getElementById("camera");
    const canvas = document.getElementById("captura");
    const preview = document.getElementById("fotoPreview");
    const placeholder = document.getElementById("cameraPlaceholder");
    const contador = document.getElementById("contadorCaptura");

    const btnRegistrar = document.getElementById(
        "btnRegistrarPonto"
    );

    const locationStatus = document.getElementById(
        "locationStatus"
    );

    const syncStatus = document.getElementById(
        "syncStatus"
    );

    const campoColaborador = document.getElementById(
        "colaboradorId"
    );

    if (
        !video
        || !canvas
        || !btnRegistrar
        || !campoColaborador
    ) {
        return;
    }

    const colaboradorId = campoColaborador.value;

    let stream = null;
    let processando = false;


    function agoraLocal() {
        return new Date();
    }


    function atualizarRelogio() {
        const relogio = document.getElementById(
            "relogio"
        );

        if (relogio) {
            relogio.textContent = (
                agoraLocal()
                .toLocaleTimeString("pt-BR")
            );
        }
    }


    atualizarRelogio();

    setInterval(
        atualizarRelogio,
        1000
    );


    function criarUuid() {
        if (
            window.crypto
            && crypto.randomUUID
        ) {
            return crypto.randomUUID();
        }

        return (
            `${Date.now()}-`
            + `${Math.random()}`
        );
    }


    function obterDispositivoId() {
        let dispositivoId = localStorage.getItem(
            "msm_device_id"
        );

        if (!dispositivoId) {
            dispositivoId = criarUuid();

            localStorage.setItem(
                "msm_device_id",
                dispositivoId
            );
        }

        return dispositivoId;
    }


    function mostrarMensagem(
        tipo,
        mensagem
    ) {
        if (!syncStatus) {
            return;
        }

        syncStatus.innerHTML = `
            <div class="alert alert-${tipo}">
                ${mensagem}
            </div>
        `;
    }


    async function ativarCamera() {
        if (
            !navigator.mediaDevices
            || !navigator.mediaDevices.getUserMedia
        ) {
            throw new Error(
                "A câmera não está disponível neste navegador."
            );
        }

        stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: "user",

                width: {
                    ideal: 1280,
                },

                height: {
                    ideal: 720,
                },
            },

            audio: false,
        });

        video.srcObject = stream;

        video.style.display = "block";
        preview.style.display = "none";
        placeholder.style.display = "none";

        await video.play();

        await new Promise((resolve) => {
            if (
                video.readyState >= 2
                && video.videoWidth > 0
            ) {
                resolve();
                return;
            }

            video.addEventListener(
                "loadeddata",
                resolve,
                {
                    once: true,
                }
            );
        });
    }


    function encerrarCamera() {
        if (!stream) {
            return;
        }

        stream.getTracks().forEach(
            (trilha) => trilha.stop()
        );

        stream = null;
        video.srcObject = null;
    }


    function esperar(milissegundos) {
        return new Promise(
            (resolve) => {
                setTimeout(
                    resolve,
                    milissegundos
                );
            }
        );
    }


    async function iniciarContagem() {
        contador.style.display = "block";

        for (
            let numero = 3;
            numero >= 1;
            numero -= 1
        ) {
            contador.textContent = numero;

            await esperar(1000);
        }

        contador.style.display = "none";
    }


    function capturarFoto() {
        return new Promise(
            (resolve, reject) => {
                const largura = (
                    video.videoWidth
                    || 720
                );

                const altura = (
                    video.videoHeight
                    || 720
                );

                if (
                    !largura
                    || !altura
                ) {
                    reject(
                        new Error(
                            "A câmera ainda não está pronta."
                        )
                    );

                    return;
                }

                canvas.width = largura;
                canvas.height = altura;

                const contexto = canvas.getContext(
                    "2d"
                );

                contexto.drawImage(
                    video,
                    0,
                    0,
                    largura,
                    altura
                );

                canvas.toBlob(
                    (fotoBlob) => {
                        if (!fotoBlob) {
                            reject(
                                new Error(
                                    "Não foi possível capturar a fotografia."
                                )
                            );

                            return;
                        }

                        preview.src = URL.createObjectURL(
                            fotoBlob
                        );

                        preview.style.display = "block";
                        video.style.display = "none";
                        placeholder.style.display = "none";

                        resolve(fotoBlob);
                    },
                    "image/jpeg",
                    0.88
                );
            }
        );
    }


    function obterLocalizacao() {
        return new Promise(
            (resolve) => {
                if (!navigator.geolocation) {
                    locationStatus.innerHTML = `
                        <i class="bi bi-exclamation-triangle text-warning me-1"></i>
                        GPS indisponível. O ponto será enviado sem validação de local.
                    `;

                    resolve(null);
                    return;
                }

                locationStatus.innerHTML = `
                    <span class="spinner-border spinner-border-sm me-1"></span>
                    Obtendo localização...
                `;

                navigator.geolocation.getCurrentPosition(
                    (posicao) => {
                        const localizacao = {
                            latitude:
                                posicao.coords.latitude,

                            longitude:
                                posicao.coords.longitude,

                            precisao:
                                posicao.coords.accuracy,
                        };

                        locationStatus.innerHTML = `
                            <i class="bi bi-geo-alt-fill text-success me-1"></i>
                            Localização obtida · precisão aproximada de
                            ${Math.round(posicao.coords.accuracy)} m
                        `;

                        resolve(localizacao);
                    },

                    () => {
                        locationStatus.innerHTML = `
                            <i class="bi bi-exclamation-triangle text-warning me-1"></i>
                            Não foi possível obter o GPS. O ponto será enviado sem validação de local.
                        `;

                        resolve(null);
                    },

                    {
                        enableHighAccuracy: true,
                        timeout: 15000,
                        maximumAge: 30000,
                    }
                );
            }
        );
    }


    function carregarFilaOffline() {
        try {
            return JSON.parse(
                localStorage.getItem(
                    "msm_ponto_offline"
                )
                || "[]"
            );
        } catch {
            return [];
        }
    }


    function salvarNaFilaOffline(item) {
        const fila = carregarFilaOffline();

        fila.push(item);

        localStorage.setItem(
            "msm_ponto_offline",
            JSON.stringify(fila)
        );
    }


    function blobParaBase64(blob) {
        return new Promise(
            (resolve, reject) => {
                const leitor = new FileReader();

                leitor.onloadend = () => {
                    resolve(leitor.result);
                };

                leitor.onerror = () => {
                    reject(
                        new Error(
                            "Não foi possível guardar a fotografia."
                        )
                    );
                };

                leitor.readAsDataURL(blob);
            }
        );
    }


    function base64ParaBlob(dataUrl) {
        const partes = dataUrl.split(",");

        const cabecalho = partes[0];
        const dados = partes[1];

        const correspondencia = cabecalho.match(
            /:(.*?);/
        );

        const mime = (
            correspondencia
            ? correspondencia[1]
            : "image/jpeg"
        );

        const binario = atob(dados);

        const bytes = new Uint8Array(
            binario.length
        );

        for (
            let indice = 0;
            indice < binario.length;
            indice += 1
        ) {
            bytes[indice] = (
                binario.charCodeAt(indice)
            );
        }

        return new Blob(
            [bytes],
            {
                type: mime,
            }
        );
    }


    async function enviarRegistro(
        registro,
        foto
    ) {
        const formulario = new FormData();

        Object.entries(registro).forEach(
            ([chave, valor]) => {
                if (
                    valor !== null
                    && valor !== undefined
                    && valor !== ""
                ) {
                    formulario.append(
                        chave,
                        valor
                    );
                }
            }
        );

        formulario.append(
            "foto",
            foto,
            "ponto.jpg"
        );

        const resposta = await fetch(
            "/api/ponto/registrar",
            {
                method: "POST",
                body: formulario,
            }
        );

        let dados;

        try {
            dados = await resposta.json();
        } catch {
            throw new Error(
                "O servidor retornou uma resposta inválida."
            );
        }

        if (
            !resposta.ok
            || !dados.ok
        ) {
            throw new Error(
                dados.erro
                || "Falha ao registrar o ponto."
            );
        }

        return dados;
    }


    async function registrarPonto() {
        if (processando) {
            return;
        }

        processando = true;

        btnRegistrar.disabled = true;

        const textoOriginal = btnRegistrar.innerHTML;

        btnRegistrar.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2"></span>
            Preparando registro...
        `;

        mostrarMensagem(
            "info",
            "Autorize o uso da câmera e da localização quando o navegador solicitar."
        );

        try {
            const promessaLocalizacao = obterLocalizacao();

            await ativarCamera();

            mostrarMensagem(
                "info",
                "Posicione o rosto diante da câmera. A fotografia será tirada automaticamente."
            );

            await iniciarContagem();

            const fotoBlob = await capturarFoto();

            encerrarCamera();

            const localizacao = await promessaLocalizacao;

            const registro = {
                client_uuid:
                    criarUuid(),

                colaborador_id:
                    colaboradorId,

                capturado_em:
                    agoraLocal().toISOString(),

                latitude:
                    localizacao?.latitude,

                longitude:
                    localizacao?.longitude,

                precisao_metros:
                    localizacao?.precisao,

                dispositivo_id:
                    obterDispositivoId(),

                dispositivo_info:
                    navigator.userAgent,
            };

            mostrarMensagem(
                "info",
                `
                    <span class="spinner-border spinner-border-sm me-1"></span>
                    Registrando ponto...
                `
            );

            if (!navigator.onLine) {
                salvarNaFilaOffline({
                    registro,
                    fotoBase64:
                        await blobParaBase64(
                            fotoBlob
                        ),
                });

                mostrarMensagem(
                    "warning",
                    `
                        <i class="bi bi-cloud-slash me-1"></i>
                        Sem internet. O ponto foi guardado neste aparelho e será sincronizado automaticamente.
                    `
                );

                return;
            }

            const dados = await enviarRegistro(
                registro,
                fotoBlob
            );

            let situacaoArea = "";

            if (
                dados.dentro_geocerca === true
            ) {
                situacaoArea = (
                    " · dentro da área permitida"
                );
            } else if (
                dados.dentro_geocerca === false
            ) {
                situacaoArea = (
                    " · fora da área permitida"
                );
            }

            mostrarMensagem(
                "success",
                `
                    <strong>
                        <i class="bi bi-check-circle me-1"></i>
                        Ponto registrado!
                    </strong>

                    <br>

                    ${dados.tipo}${situacaoArea}
                `
            );

            setTimeout(
                () => {
                    window.location.reload();
                },
                1500
            );

        } catch (erro) {
            encerrarCamera();

            preview.style.display = "none";
            placeholder.style.display = "flex";

            mostrarMensagem(
                "danger",
                `
                    <i class="bi bi-exclamation-triangle me-1"></i>
                    ${erro.message}
                `
            );

        } finally {
            processando = false;

            btnRegistrar.disabled = false;
            btnRegistrar.innerHTML = textoOriginal;
        }
    }


    async function sincronizarFila() {
        if (!navigator.onLine) {
            return;
        }

        const fila = carregarFilaOffline();

        if (!fila.length) {
            return;
        }

        const restantes = [];

        for (const item of fila) {
            try {
                await enviarRegistro(
                    item.registro,
                    base64ParaBlob(
                        item.fotoBase64
                    )
                );

            } catch {
                restantes.push(item);
            }
        }

        localStorage.setItem(
            "msm_ponto_offline",
            JSON.stringify(restantes)
        );

        if (!restantes.length) {
            mostrarMensagem(
                "success",
                `
                    <i class="bi bi-cloud-check me-1"></i>
                    Marcações pendentes sincronizadas.
                `
            );

            setTimeout(
                () => {
                    window.location.reload();
                },
                1200
            );
        }
    }


    btnRegistrar.addEventListener(
        "click",
        registrarPonto
    );

    window.addEventListener(
        "online",
        sincronizarFila
    );

    window.addEventListener(
        "beforeunload",
        encerrarCamera
    );

    sincronizarFila();
})();