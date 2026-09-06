// Transparent bidirectional clipboard synchronization bridge for noVNC
(function() {
    console.log("[win32-vnc-k8s] Initializing transparent clipboard bridge...");

    // Guest -> Host: Intercept noVNC received clipboard event and write to browser
    const originalReceive = UI.clipboardReceive;
    UI.clipboardReceive = function(e) {
        if (originalReceive) originalReceive(e);
        const text = e.detail ? e.detail.text : null;
        if (navigator.clipboard && navigator.clipboard.writeText && text) {
            navigator.clipboard.writeText(text).catch(() => {
                // Background focus restrictions may prevent automatic write without focus
            });
        }
    };

    // Host -> Guest: Transparent sync on browser window focus
    window.addEventListener('focus', () => {
        if (navigator.clipboard && navigator.clipboard.readText) {
            navigator.clipboard.readText().then(text => {
                if (text && UI.rfb) {
                    UI.rfb.clipboardPasteFrom(text);
                }
            }).catch(() => {
                // Silent catch if user denied clipboard permissions
            });
        }
    });

    window.UI = UI;
    if (window.top !== window) {
        window.top.noVNC_UI = UI;
    }
    console.log("[win32-vnc-k8s] Transparent clipboard bridge active.");
})();
