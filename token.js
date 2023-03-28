/**
 * Generating token for Mimbus
 */

const AppTicket = require('steam-appticket');
const SteamUser = require('steam-user');
const net = require('net');

const APP_ID = 2 * 5 * 13 * 17 * 19 * 47;  // Mimbus app id

function buf2hex(buffer) { // buffer is an ArrayBuffer
    return [...new Uint8Array(buffer)]
        .map(x => x.toString(16).padStart(2, '0'))
        .join('');
}

async function getToken(client) {
    let result = await client.createAuthSessionTicket(APP_ID);

    let parsedTicket = AppTicket.parseAppTicket(result.sessionTicket);
    let hexTicket = buf2hex(result.sessionTicket).toUpperCase();

    await client.activateAuthSessionTickets(APP_ID, [parsedTicket]);

    return hexTicket
}

let unixServer = net.createServer(async (socket) => {
    try {
        let client = new SteamUser({dataDirectory: 'sentry_files', debug: true});

        let guardCallback = undefined;
        let rememberPassword = false;

        // read steam credentials from socket
        socket.on('data', (data) => {
            let length = data.readInt32LE(0);
            let request = JSON.parse(data.slice(4, length + 4).toString());

            if (request.code) {
                guardCallback(request.code);
            } else if (request.credentials) {
                client.logOn(request.credentials);

                if (request.credentials.rememberPassword) {
                    rememberPassword = true;
                }
            }
        });

        client.on('loggedOn', async function () {
            let token = await getToken(client);

            let refreshToken = null;
            if (rememberPassword) {
                refreshToken = await new Promise(resolve => client.on('loginKey', resolve));
            }

            let response = JSON.stringify({token: token, refreshToken: refreshToken});
            let length = Buffer.byteLength(response);

            const buffer = new ArrayBuffer(4);
            const view = new DataView(buffer);
            view.setInt32(0, length);

            client.logOff();

            socket.write(Buffer.concat([Buffer.from(buffer), Buffer.from(response)]));
            socket.end();
        });

        client.on('error', function (err) {
            console.error(err)
            let response = JSON.stringify({error: err.message});
            let length = Buffer.byteLength(response);

            const buffer = new ArrayBuffer(4);
            const view = new DataView(buffer);
            view.setInt32(0, length);

            socket.write(Buffer.concat([Buffer.from(buffer), Buffer.from(response)]));
        });

        client.on('steamGuard', function (_, callback) {
            console.log('Guard required');
            let response = JSON.stringify({guard: true});
            let length = Buffer.byteLength(response);

            const buffer = new ArrayBuffer(4);
            const view = new DataView(buffer);
            view.setInt32(0, length);

            socket.write(Buffer.concat([Buffer.from(buffer), Buffer.from(response)]));

            guardCallback = callback;
        });

    } catch (e) {
        let response = JSON.stringify({error: e.message});
        let length = Buffer.byteLength(response);

        const buffer = new ArrayBuffer(4);
        const view = new DataView(buffer);
        view.setInt32(0, length);

        socket.write(Buffer.concat([Buffer.from(buffer), Buffer.from(response)]));
    }

});

// start unix socket server
unixServer.listen('/tmp/mimbus-token.sock');

process.on('SIGINT', function () {
    unixServer.close();
    process.exit();
});
