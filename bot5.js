#!/usr/bin/env node
const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { URLSearchParams } = require('url');

// ============================================================
// CONFIG
// ============================================================
const CONFIG = {
    baseUrl: 'https://freeltc.fun',
    loginUrl: 'https://freeltc.fun/login',
    authUrl: 'https://freeltc.fun/auth/login',
    faucetUrl: 'https://freeltc.fun/faucet',
    verifyUrl: 'https://freeltc.fun/faucet/verify',
    email: 'arasarathinan@gmail.com',
    password: 'Money12$$',
    
    proxy: {
        host: '82.26.234.92',
        port: 6240,
        username: 'Venu1234',
        password: 'Venu1234'
    },
    
    captcha: {
        apiKey: 'X1iRqWL1pv1bpvHRfvqeXxQqYhcERDti',
        apiUrl: 'https://157.180.15.203/in.php',
        resultUrl: 'https://157.180.15.203/res.php',
        sitekey: 'jschallenge',
        pollInterval: 5,
        maxWait: 300
    }
};

// ============================================================
// SESSION
// ============================================================
const SESSION_FILE = 'sessiogdhn.json';
let cookieJar = '';
let additionalHeaders = {};
let totalClaims = 0;
let totalEarned = 0;

function saveSession() {
    fs.writeFileSync(SESSION_FILE, JSON.stringify({ cookieJar, additionalHeaders }));
}

function loadSession() {
    if (fs.existsSync(SESSION_FILE)) {
        try {
            const data = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf8'));
            cookieJar = data.cookieJar || '';
            additionalHeaders = data.additionalHeaders || {};
            return true;
        } catch (e) {}
    }
    return false;
}

// ============================================================
// PROXY
// ============================================================
const HttpsProxyAgent = require('https-proxy-agent');
const HttpProxyAgent = require('http-proxy-agent');
const proxyUrl = `http://${CONFIG.proxy.username}:${CONFIG.proxy.password}@${CONFIG.proxy.host}:${CONFIG.proxy.port}`;
const httpsAgent = new HttpsProxyAgent.HttpsProxyAgent(proxyUrl);
const httpAgent = new HttpProxyAgent.HttpProxyAgent(proxyUrl);

function createClient() {
    return axios.create({
        httpAgent, httpsAgent,
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Cookie': cookieJar,
            ...additionalHeaders
        },
        maxRedirects: 5,
        validateStatus: () => true,
        timeout: 15000
    });
}

// ============================================================
// HELPERS
// ============================================================
const sleep = ms => new Promise(r => setTimeout(r, ms));

function updateCookies(res) {
    const cookies = res.headers['set-cookie'];
    if (!cookies) return;
    (Array.isArray(cookies) ? cookies : [cookies]).forEach(c => {
        const [nv] = c.split(';');
        const [name, ...val] = nv.split('=');
        const value = val.join('=');
        if (!name || value === undefined) return;
        cookieJar = cookieJar.includes(name + '=')
            ? cookieJar.replace(new RegExp(name + '=[^;]*'), name + '=' + value)
            : cookieJar + (cookieJar ? '; ' : '') + name + '=' + value;
    });
    saveSession();
}

// ============================================================
// CLOUDFLARE SOLVER
// ============================================================
async function solveCF(pageUrl) {
    console.log('🔧 Solving Cloudflare...');
    const proxyStr = `${CONFIG.proxy.host}:${CONFIG.proxy.port}:${CONFIG.proxy.username}:${CONFIG.proxy.password}`;
    
    const params = new URLSearchParams({
        key: CONFIG.captcha.apiKey,
        method: 'turnstile',
        pageurl: pageUrl,
        sitekey: CONFIG.captcha.sitekey,
        proxy: proxyStr
    });
    
    const r1 = await axios.get(`${CONFIG.captcha.apiUrl}?${params}`, { timeout: 10000 });
    if (!r1.data.includes('|')) throw new Error('CF create failed');
    const taskId = r1.data.split('|')[1];
    
    const start = Date.now();
    while ((Date.now() - start) / 1000 < CONFIG.captcha.maxWait) {
        await sleep(CONFIG.captcha.pollInterval * 1000);
        
        const poll = new URLSearchParams({
            key: CONFIG.captcha.apiKey,
            id: taskId,
            action: 'get'
        });
        
        const r2 = await axios.get(`${CONFIG.captcha.resultUrl}?${poll}`, { timeout: 10000 });
        const result = r2.data;
        
        if (result.includes('OK|') && !result.includes('NOT_READY')) {
            let data = result.startsWith('OK|') ? result.substring(3) : result;
            const json = JSON.parse(Buffer.from(data, 'base64').toString('utf-8'));
            
            const cf = json.cf_clearence || json.cf_clearance;
            if (cf) {
                cookieJar = cookieJar.includes('cf_clearance=')
                    ? cookieJar.replace(/cf_clearance=[^;]*/, 'cf_clearance=' + cf)
                    : cookieJar + (cookieJar ? '; ' : '') + 'cf_clearance=' + cf;
            }
            if (json.headers_list) Object.assign(additionalHeaders, json.headers_list);
            saveSession();
            console.log('✅ Cloudflare solved!');
            return;
        }
    }
    throw new Error('CF timeout');
}

// ============================================================
// HTTP REQUESTS
// ============================================================
async function GET(url) {
    const c = createClient();
    const r = await c.get(url);
    updateCookies(r);
    return { cf: r.status === 403, data: r.data, status: r.status, headers: r.headers };
}

async function POST(url, payload, extraHeaders = {}) {
    const c = createClient();
    const r = await c.post(url, payload.toString(), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', ...extraHeaders }
    });
    updateCookies(r);
    return { cf: r.status === 403, data: r.data, status: r.status, headers: r.headers };
}

// ============================================================
// CSRF TOKEN
// ============================================================
function getCsrf(html) {
    const $ = cheerio.load(html);
    return $('input[name="csrf_token_name"]').val() || $('#token').val() || '';
}

// ============================================================
// ANTI-BOT SOLVER - CALLS ocr.py
// ============================================================
async function solveAntibot(html) {
    console.log('🤖 Solving anti-bot via OCR...');
    
    // Save HTML to local temp file
    const tempFile = path.join(__dirname, 'temp_faucet.html');
    
    try {
        fs.writeFileSync(tempFile, html);
        console.log('→ HTML saved, calling ocr.py...');
        
        // Call ocr.py
        const result = execSync(`python3 ocr.py "${tempFile}"`, {
            encoding: 'utf-8',
            timeout: 120000,
            stdio: ['pipe', 'pipe', 'pipe']
        });
        
        // Parse JSON output (last line)
        const lines = result.trim().split('\n');
        const lastLine = lines[lines.length - 1];
        
        console.log('→ OCR output:', lastLine);
        
        const json = JSON.parse(lastLine);
        
        if (json.success && json.solution) {
            console.log(`→ Solution: "${json.solution}"`);
            return json.solution;
        } else {
            console.log('→ OCR failed:', json.error || 'Unknown error');
            return null;
        }
    } catch (error) {
        console.error('→ OCR error:', error.message);
        if (error.stdout) console.error('stdout:', error.stdout);
        if (error.stderr) console.error('stderr:', error.stderr);
        return null;
    } finally {
        // Cleanup
        try { fs.unlinkSync(tempFile); } catch (e) {}
    }
}

// ============================================================
// PAGE HELPERS
// ============================================================
function getTimer(html) {
    const $ = cheerio.load(html);
    return (parseInt($('#minute').text()) || 0) * 60 + (parseInt($('#second').text()) || 0);
}

function getClaims(html) {
    const $ = cheerio.load(html);
    const el = $('.small.text-muted').filter((i, e) => $(e).text().includes('Claims Left'));
    return el.length ? (parseInt(el.first().next('strong').text()) || 0) : -1;
}

function checkResult(html) {
    const $ = cheerio.load(html);
    const success = $('.alert-success').text().trim();
    const danger = $('.alert-danger').text().trim();
    
    if (success.includes('Claim Successful')) {
        const amt = (success.match(/([\d.]+)\s*LTC/) || [])[1] || '0';
        console.log(`✅ ${success}`);
        return { ok: true, amount: amt };
    }
    if (danger) console.log(`❌ ${danger}`);
    return { ok: false };
}

async function waitTimer(sec) {
    if (sec <= 0) return;
    process.stdout.write(`⏳ Timer ${sec}s: `);
    for (let i = sec; i > 0; i--) {
        process.stdout.write(`${i} `);
        await sleep(1000);
    }
    console.log('✓');
}

// ============================================================
// LOGIN
// ============================================================
async function checkLogin() {
    console.log('🔍 Checking session...');
    let res = await GET(CONFIG.baseUrl);
    if (res.cf) { await solveCF(CONFIG.baseUrl); res = await GET(CONFIG.baseUrl); }
    
    if (res.data) {
        const $ = cheerio.load(res.data);
        if ($('title').text().includes('Dashboard')) {
            console.log('✅ Already logged in!');
            return true;
        }
    }
    console.log('⚠️ Need to login');
    return false;
}

async function login() {
    console.log('🔐 Logging in...');
    
    let res = await GET(CONFIG.loginUrl);
    if (res.cf) { await solveCF(CONFIG.loginUrl); res = await GET(CONFIG.loginUrl); }
    if (!res.data) throw new Error('No login page');
    
    const csrf = getCsrf(res.data);
    console.log(`→ CSRF: ${csrf}`);
    
    const payload = new URLSearchParams({
        csrf_token_name: csrf,
        email: CONFIG.email,
        password: CONFIG.password
    });
    
    let r2 = await POST(CONFIG.authUrl, payload);
    if (r2.cf) { await solveCF(CONFIG.authUrl); r2 = await POST(CONFIG.authUrl, payload); }
    
    if (r2.status === 302 && r2.headers.location) {
        const loc = r2.headers.location;
        await GET(loc.startsWith('http') ? loc : CONFIG.baseUrl + loc);
    }
    
    saveSession();
    console.log('✅ Logged in successfully!');
}

// ============================================================
// CLAIM
// ============================================================
async function doClaim() {
    console.log(`\n${'═'.repeat(50)}`);
    console.log(`💧 CLAIM #${totalClaims + 1}`);
    console.log('═'.repeat(50));
    
    let res = await GET(CONFIG.faucetUrl);
    if (res.cf) { await solveCF(CONFIG.faucetUrl); res = await GET(CONFIG.faucetUrl); }
    if (!res.data) throw new Error('No faucet page');
    
    const claims = getClaims(res.data);
    console.log(`→ Claims left: ${claims}`);
    if (claims === 0) return { stop: true };
    
    const timer = getTimer(res.data);
    if (timer > 0) {
        console.log(`→ Timer: ${timer}s`);
        await waitTimer(timer);
        res = await GET(CONFIG.faucetUrl);
        if (res.cf) { await solveCF(CONFIG.faucetUrl); res = await GET(CONFIG.faucetUrl); }
        if (!res.data) return { wait: true };
    }
    
    const csrf = getCsrf(res.data);
    console.log(`→ CSRF: ${csrf.substring(0, 10)}...`);
    
    // Solve anti-bot using ocr.py
    const solution = await solveAntibot(res.data);
    if (!solution) {
        console.log('⚠️ Anti-bot solve failed, retrying...');
        return { wait: true };
    }
    
    console.log(`→ Final solution: "${solution}"`);
    
    // Verify
    const payload = new URLSearchParams({
        antibotlinks: solution,
        csrf_token_name: csrf
    });
    
    let vrf = await POST(CONFIG.verifyUrl, payload, {
        Origin: CONFIG.baseUrl,
        Referer: CONFIG.faucetUrl
    });
    
    if (vrf.cf) {
        await solveCF(CONFIG.verifyUrl);
        vrf = await POST(CONFIG.verifyUrl, payload, {
            Origin: CONFIG.baseUrl,
            Referer: CONFIG.faucetUrl
        });
    }
    
    if (vrf.data) {
        const result = checkResult(vrf.data);
        const newTimer = getTimer(vrf.data);
        const newClaims = getClaims(vrf.data);
        
        if (result.ok) {
            totalClaims++;
            totalEarned += parseFloat(result.amount);
            console.log(`💰 Total: ${totalClaims} claims | ${totalEarned.toFixed(8)} LTC`);
        }
        
        return { stop: newClaims === 0, timer: newTimer, success: result.ok };
    }
    
    return { wait: true };
}

// ============================================================
// MAIN LOOP
// ============================================================
async function main() {
    console.log('🚀 FreeLTC Auto Claim - OCR Solver');
    console.log(`📧 ${CONFIG.email}`);
    console.log(`🌐 Proxy: ${CONFIG.proxy.host}:${CONFIG.proxy.port}\n`);
    
    loadSession();
    
    if (!(await checkLogin())) {
        await login();
    }
    
    while (true) {
        try {
            const result = await doClaim();
            
            if (result.stop) {
                console.log('\n🛑 No claims left! Stopping...');
                break;
            }
            
            if (result.timer > 0) {
                await waitTimer(result.timer);
            } else if (result.wait) {
                console.log('⏳ Waiting 3s...');
                await sleep(3000);
            } else {
                await sleep(2000);
            }
        } catch (error) {
            console.error(`❌ Error: ${error.message}`);
            if (error.message.includes('Cloudflare') || error.message.includes('403')) {
                try { await solveCF(CONFIG.faucetUrl); } catch (e) {}
                continue;
            }
            console.log('⏳ Waiting 10s before retry...');
            await sleep(10000);
        }
    }
    
    console.log(`\n🎉 COMPLETED!`);
    console.log(`📊 Total Claims: ${totalClaims}`);
    console.log(`💰 Total Earned: ${totalEarned.toFixed(8)} LTC`);
}

main().catch(error => {
    console.error('💥 Fatal error:', error.message);
    process.exit(1);
});

process.on('SIGINT', () => {
    saveSession();
    console.log(`\n\n👋 Stopped | Claims: ${totalClaims} | Earned: ${totalEarned.toFixed(8)} LTC`);
    process.exit(0);
});
