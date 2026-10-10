const PROTOCOLS = {
    'h3': 'HTTP/3',
    'h2': 'HTTP/2',
    'http/1.1': 'HTTP/1.1',
};

// Added by Firefox itself, never sent by the server
const SYNTHETIC = ['x-firefox-spdy'];

const block = document.getElementById('headers');
const caption = document.getElementById('fetched-at');

block.textContent = 'Requesting…';

fetch('/api/v1/ping', { cache: 'no-store' })
    .then(async (response) => {
        const body = await response.text();

        // The timing entry exists only once the body has been read
        const timing = performance.getEntriesByName(response.url).pop();
        const protocol = PROTOCOLS[timing?.nextHopProtocol] ?? 'HTTP';

        const lines = [`${protocol} ${response.status}`];
        for (const [name, value] of response.headers) {
            if (!SYNTHETIC.includes(name)) {
                lines.push(`${name}: ${value}`);
            }
        }

        block.textContent = `${lines.join('\n')}\n\n${body}`;
        caption.textContent = `Fetched from this server at ${new Date().toLocaleTimeString()}.`;
    })
    .catch(() => {
        block.textContent = 'The request failed. Run the command above: what it prints is what this block would have shown.';
    });
