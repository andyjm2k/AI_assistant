window.runWorkflow = async function(contentPrompt, options = {}) {
    console.log('ai-autogen-call.js - runWorkflow called with:', contentPrompt);

    // Capture hostname from calling page - use provided hostname, or fallback to window.location
    // This ensures we use the actual calling page's hostname, not localhost
    const hostname = options.hostname || window.location.hostname;
    const protocol = options.protocol || window.location.protocol;
    const currentPort = window.location.port ? parseInt(window.location.port) : (protocol === 'https:' ? 443 : 80);
    const proxyPort = 8002; // Proxy server runs on port 8002

    const endpointPath = '/v1/proxy/autogen';

    // Build candidate URLs - only use same-origin if we're already on the proxy port
    // Otherwise skip it to avoid 501 errors from the static file server
    const candidateUrls = [];
    
    // Only add same-origin URL if we're already on the proxy server's port
    if (currentPort === proxyPort) {
        candidateUrls.push(endpointPath);
    }
    
    // Add the explicit proxy URL (always needed for direct deployments)
    const configuredProxyUrl = window.PROXY_BASE_URL
        ? `${window.PROXY_BASE_URL}${endpointPath}`
        : `${protocol}//${hostname}:${proxyPort}${endpointPath}`;
    candidateUrls.push(configuredProxyUrl);

    if (protocol === 'https:') {
        // Last-resort fallback when proxy is only exposed over HTTP.
        // This may still be blocked by mixed-content rules depending on deployment.
        const httpFallback = `http://${hostname}:${proxyPort}${endpointPath}`;
        candidateUrls.push(httpFallback);
    }

    let lastError = null;

    try {
        for (const targetUrl of candidateUrls) {
            try {
                console.log('ai-autogen-call.js - Trying proxy URL:', targetUrl);

                const response = await fetch(targetUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        input: contentPrompt
                    })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status} - ${response.statusText}`);
                }

                const data = await response.json();
                console.log('Autogen API response:', data);

                const transcript =
                    data.log_content ||
                    data.response ||
                    data.output ||
                    data.result ||
                    data.message ||
                    JSON.stringify(data, null, 2);

                if (options.fullPayload) {
                    return {
                        transcript,
                        response: data.response || transcript,
                        output: data.output || transcript,
                        summary: data.summary || '',
                        logFile: data.log_file || data.logFile || '',
                        messages: Array.isArray(data.messages) ? data.messages : [],
                        raw: data
                    };
                }

                return transcript;
            } catch (error) {
                lastError = error;
                console.warn('ai-autogen-call.js - Request failed for URL:', targetUrl, error);
            }
        }

        throw lastError || new Error('Failed to reach AutoGen proxy endpoint.');
    } catch (error) {
        console.error('ai-autogen-call.js - Error:', error);
        throw error;
    }
};

// Optional: Add a check when the script loads
console.log('ai-autogen-call.js loaded, runWorkflow function available:', !!window.runWorkflow);
