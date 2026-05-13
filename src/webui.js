// webui.js
(function() {
    const SVG_NS = "http://www.w3.org/2000/svg";

    // Konfiguration
    const RECT_W = 100;
    const RECT_H = 40;
    const GAP = 20;
    const PROXY_CENTER_Y = 210;
    const CLIENT_X = 50;
    const CONTAINER_X = 480;
    const PROXY_LEFT = 265;
    const PROXY_RIGHT = 415;
    const PROXY_MID_Y = 210;

    function clearDynamicElements() {
        const svg = document.getElementById('dashboard');
        if (!svg) return;
        svg.querySelectorAll('.dynamic').forEach(el => el.remove());
    }

    function drawDashboard(ids) {
        const svg = document.getElementById('dashboard');
        if (!svg) {
            console.warn('SVG #dashboard nicht gefunden – zeichnen abgebrochen');
            return;
        }

        clearDynamicElements();

        if (!ids || ids.length === 0) return;

        const n = ids.length;
        const totalHeight = n * RECT_H + (n - 1) * GAP;
        let startY = PROXY_CENTER_Y - totalHeight / 2;

        for (let i = 0; i < n; i++) {
            const id = ids[i];
            const y = startY + i * (RECT_H + GAP);
            const clientCenterX = CLIENT_X + RECT_W;
            const containerCenterX = CONTAINER_X;
            const centerY = y + RECT_H / 2;

            // Client-Rechteck
            const clientRect = document.createElementNS(SVG_NS, 'rect');
            clientRect.setAttribute('x', CLIENT_X);
            clientRect.setAttribute('y', y);
            clientRect.setAttribute('width', RECT_W);
            clientRect.setAttribute('height', RECT_H);
            clientRect.setAttribute('rx', '8');
            clientRect.setAttribute('fill', '#4A90E2');
            clientRect.setAttribute('stroke', '#FFEAD6');
            clientRect.setAttribute('stroke-width', '1.5');
            clientRect.classList.add('dynamic');
            svg.appendChild(clientRect);

            // Client-Text
            const clientText = document.createElementNS(SVG_NS, 'text');
            clientText.textContent = `Client ${id}`;
            clientText.setAttribute('x', CLIENT_X + RECT_W / 2);
            clientText.setAttribute('y', y + RECT_H / 2);
            clientText.setAttribute('text-anchor', 'middle');
            clientText.setAttribute('dominant-baseline', 'middle');
            clientText.setAttribute('font-family', 'sans-serif');
            clientText.setAttribute('font-size', '14');
            clientText.setAttribute('fill', '#EEEAE8');
            clientText.classList.add('dynamic');
            svg.appendChild(clientText);

            // Container-Rechteck
            const containerRect = document.createElementNS(SVG_NS, 'rect');
            containerRect.setAttribute('x', CONTAINER_X);
            containerRect.setAttribute('y', y);
            containerRect.setAttribute('width', RECT_W);
            containerRect.setAttribute('height', RECT_H);
            containerRect.setAttribute('rx', '8');
            containerRect.setAttribute('fill', '#50B883');
            containerRect.setAttribute('stroke', '#FFEAD6');
            containerRect.setAttribute('stroke-width', '1.5');
            containerRect.classList.add('dynamic');
            svg.appendChild(containerRect);

            // Container-Text
            const containerText = document.createElementNS(SVG_NS, 'text');
            containerText.textContent = `Container ${id}`;
            containerText.setAttribute('x', CONTAINER_X + RECT_W / 2);
            containerText.setAttribute('y', y + RECT_H / 2);
            containerText.setAttribute('text-anchor', 'middle');
            containerText.setAttribute('dominant-baseline', 'middle');
            containerText.setAttribute('font-family', 'sans-serif');
            containerText.setAttribute('font-size', '14');
            containerText.setAttribute('fill', '#EEEAE8');
            containerText.classList.add('dynamic');
            svg.appendChild(containerText);

            // Pfeil Client → Proxy
            const arrow1 = document.createElementNS(SVG_NS, 'line');
            arrow1.setAttribute('x1', clientCenterX);
            arrow1.setAttribute('y1', centerY);
            arrow1.setAttribute('x2', PROXY_LEFT);
            arrow1.setAttribute('y2', PROXY_MID_Y);
            arrow1.setAttribute('stroke', '#FFEAD6');
            arrow1.setAttribute('stroke-width', '2');
            arrow1.classList.add('dynamic');
            svg.appendChild(arrow1);

            // Pfeil Proxy → Container
            const arrow2 = document.createElementNS(SVG_NS, 'line');
            arrow2.setAttribute('x1', PROXY_RIGHT);
            arrow2.setAttribute('y1', PROXY_MID_Y);
            arrow2.setAttribute('x2', containerCenterX);
            arrow2.setAttribute('y2', centerY);
            arrow2.setAttribute('stroke', '#FFEAD6');
            arrow2.setAttribute('stroke-width', '2');
            arrow2.classList.add('dynamic');
            svg.appendChild(arrow2);
        }
    }

    function initEventSource() {
        const es = new EventSource('/events');

        es.onmessage = (e) => {
            try {
                const ids = JSON.parse(e.data);
                if (Array.isArray(ids)) {
                    drawDashboard(ids);
                } else {
                    console.warn('Kein Array empfangen:', ids);
                }
            } catch (err) {
                console.error('Fehler beim Parsen:', err);
            }
        };

        es.onerror = (err) => {
            console.error('EventSource-Fehler, Neustart in 3s', err);
            es.close();
            setTimeout(initEventSource, 3000);
        };
    }

    // Warte, bis das DOM komplett geladen ist, und prüfe zusätzlich auf SVG
    window.addEventListener('DOMContentLoaded', () => {
        // Falls das SVG noch nicht da ist (selten), kurz warten
        if (!document.getElementById('dashboard')) {
            console.warn('SVG noch nicht da, warte kurz...');
            const checkInterval = setInterval(() => {
                if (document.getElementById('dashboard')) {
                    clearInterval(checkInterval);
                    initEventSource();
                }
            }, 50);
        } else {
            initEventSource();
        }
    });
})();
