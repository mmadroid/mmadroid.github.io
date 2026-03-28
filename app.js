import { TonConnectUI } from 'https://unpkg.com/@tonconnect/ui@latest/dist/index.js';
import { TonClient, Address, fromNano, toNano } from 'https://unpkg.com/ton@latest/dist/ton.js';

// Глобальные переменные
let tonConnectUI;
let client;
let isTestnet = false; // пумолчанию mainnet
let walletAddress = null;

// Элементы DOM
const walletConnectDiv = document.getElementById('wallet-connect');
const walletInfoDiv = document.getElementById('wallet-info');
const connectBtn = document.getElementById('connect-wallet-btn');
const disconnectBtn = document.getElementById('disconnect-wallet-btn');
const copyAddressBtn = document.getElementById('copy-address-btn');
const sendTonBtn = document.getElementById('send-ton-btn');
const mainnetBtn = document.getElementById('mainnet-btn');
const testnetBtn = document.getElementById('testnet-btn');
const balanceSpan = document.getElementById('balance');
const addressSpan = document.getElementById('address');
const sendToInput = document.getElementById('send-to');
const sendAmountInput = document.getElementById('send-amount');
const sendStatusDiv = document.getElementById('send-status');
const jettonsList = document.getElementById('jettons-list');
const nftsList = document.getElementById('nfts-list');
const transactionsList = document.getElementById('transactions-list');

// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// Настройка темы Telegram
const theme = tg.themeParams;
if (theme) {
    document.documentElement.style.setProperty('--tg-theme-bg-color', theme.bg_color || '#ffffff');
    document.documentElement.style.setProperty('--tg-theme-text-color', theme.text_color || '#000000');
    document.documentElement.style.setProperty('--tg-theme-button-color', theme.button_color || '#2481cc');
    document.documentElement.style.setProperty('--tg-theme-button-text-color', theme.button_text_color || '#ffffff');
    document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', theme.secondary_bg_color || '#f5f5f5');
    document.documentElement.style.setProperty('--tg-theme-hint-color', theme.hint_color || '#cccccc');
}

// Адаптивная высота
const appDiv = document.getElementById('app');
function setAppHeight() {
    if (tg.viewportHeight) {
        document.body.style.minHeight = `${tg.viewportHeight}px`;
    }
}
setAppHeight();
tg.onEvent('viewportChanged', setAppHeight);

// Функция инициализации TON Connect
async function initTonConnect() {
    const manifestUrl = 'https://mmadroid.github.io/'; // ЗАМЕНИТЕ НА ВАШ URL
    tonConnectUI = new TonConnectUI({
        manifestUrl: manifestUrl,
        buttonRootId: 'connect-wallet-btn', // кнопка для подключения будет заменена
    });

    // Подписка на изменение статуса подключения
    tonConnectUI.onStatusChange(async (wallet) => {
        if (wallet) {
            walletAddress = wallet.account.address;
            addressSpan.innerText = walletAddress;
            walletConnectDiv.style.display = 'none';
            walletInfoDiv.style.display = 'block';
            await updateWalletData();
        } else {
            walletAddress = null;
            walletConnectDiv.style.display = 'block';
            walletInfoDiv.style.display = 'none';
            clearWalletData();
        }
    });
}

// Обновление данных кошелька (баланс, жетоны, NFT, транзакции)
async function updateWalletData() {
    if (!walletAddress) return;

    const address = Address.parse(walletAddress);
    try {
        const balance = await client.getBalance(address);
        balanceSpan.innerText = `${fromNano(balance)} TON`;
        await loadJettons(address);
        await loadNFTs(address);
        await loadTransactions(address);
    } catch (err) {
        console.error('Error updating wallet data:', err);
        tg.showAlert('Failed to load wallet data');
    }
}

// Загрузка Jettons (используем TonAPI или прямое обращение к блокчейну)
async function loadJettons(address) {
    // Здесь для простоты используем заглушку, так как получение Jettons требует сложных запросов к индексеру.
    // Рекомендуется использовать API типа https://tonapi.io
    jettonsList.innerHTML = '<div class="empty">Loading...</div>';
    try {
        // Пример запроса к TonAPI (нужен API ключ, регистрируйтесь на tonapi.io)
        const response = await fetch(`https://tonapi.io/v1/account/getInfo?address=${address.toString()}`);
        const data = await response.json();
        if (data.balances && data.balances.length > 0) {
            const jets = data.balances.filter(b => b.symbol !== 'TON');
            if (jets.length) {
                jettonsList.innerHTML = jets.map(j => `<div class="list-item">${j.balance} ${j.symbol}</div>`).join('');
                return;
            }
        }
        jettonsList.innerHTML = '<div class="empty">No jettons</div>';
    } catch (err) {
        console.error(err);
        jettonsList.innerHTML = '<div class="empty">Failed to load jettons</div>';
    }
}

// Загрузка NFT
async function loadNFTs(address) {
    nftsList.innerHTML = '<div class="empty">Loading...</div>';
    try {
        const response = await fetch(`https://tonapi.io/v1/account/getNftItems?address=${address.toString()}`);
        const data = await response.json();
        if (data.nft_items && data.nft_items.length) {
            nftsList.innerHTML = data.nft_items.map(nft => `<div class="list-item">${nft.name || nft.index}</div>`).join('');
        } else {
            nftsList.innerHTML = '<div class="empty">No NFTs</div>';
        }
    } catch (err) {
        console.error(err);
        nftsList.innerHTML = '<div class="empty">Failed to load NFTs</div>';
    }
}

// Загрузка транзакций (используем TonAPI)
async function loadTransactions(address) {
    transactionsList.innerHTML = '<div class="empty">Loading...</div>';
    try {
        const response = await fetch(`https://tonapi.io/v1/blockchain/getAccountTransactions?address=${address.toString()}&limit=10`);
        const data = await response.json();
        if (data.transactions && data.transactions.length) {
            transactionsList.innerHTML = data.transactions.map(tx => {
                const date = new Date(tx.utime * 1000).toLocaleString();
                const amount = fromNano(tx.in_msg?.value || '0');
                return `<div class="list-item">
                            <strong>${tx.in_msg?.source || '?'}</strong> → ${amount} TON<br>
                            <small>${date}</small>
                        </div>`;
            }).join('');
        } else {
            transactionsList.innerHTML = '<div class="empty">No recent transactions</div>';
        }
    } catch (err) {
        console.error(err);
        transactionsList.innerHTML = '<div class="empty">Failed to load transactions</div>';
    }
}

// Очистка данных при отключении
function clearWalletData() {
    balanceSpan.innerText = '0.00 TON';
    addressSpan.innerText = '-';
    jettonsList.innerHTML = '<div class="empty">No jettons</div>';
    nftsList.innerHTML = '<div class="empty">No NFTs</div>';
    transactionsList.innerHTML = '<div class="empty">No transactions yet</div>';
}

// Отправка TON
async function sendTon() {
    if (!tonConnectUI.connected) {
        tg.showAlert('Wallet not connected');
        return;
    }
    const to = sendToInput.value.trim();
    const amount = sendAmountInput.value.trim();
    if (!to || !amount) {
        tg.showAlert('Please enter recipient and amount');
        return;
    }
    let parsedAmount;
    try {
        parsedAmount = toNano(amount);
    } catch (e) {
        tg.showAlert('Invalid amount');
        return;
    }

    sendStatusDiv.innerText = 'Sending...';
    sendStatusDiv.style.color = 'inherit';

    try {
        const transaction = {
            validUntil: Math.floor(Date.now() / 1000) + 300, // 5 минут
            messages: [
                {
                    address: to,
                    amount: parsedAmount.toString(),
                },
            ],
        };
        const result = await tonConnectUI.sendTransaction(transaction);
        sendStatusDiv.innerText = `Transaction sent! Hash: ${result}`;
        sendStatusDiv.style.color = 'green';
        // обновить баланс и транзакции через некоторое время
        setTimeout(() => updateWalletData(), 5000);
    } catch (err) {
        console.error(err);
        sendStatusDiv.innerText = `Error: ${err.message}`;
        sendStatusDiv.style.color = 'red';
    }
}

// Копирование адреса
function copyAddress() {
    if (!walletAddress) return;
    navigator.clipboard.writeText(walletAddress);
    tg.showAlert('Address copied!');
}

// Переключение сети
function switchNetwork(isTest) {
    isTestnet = isTest;
    if (isTestnet) {
        client = new TonClient({
            endpoint: 'https://testnet.toncenter.com/api/v2/jsonRPC',
            apiKey: '8f3b3876d5397b086a1e70692334ed235f6aeb0add57669569306b659be321da' // получить на toncenter.com
        });
        mainnetBtn.classList.remove('active');
        testnetBtn.classList.add('active');
    } else {
        client = new TonClient({
            endpoint: 'https://toncenter.com/api/v2/jsonRPC',
            apiKey: 'your_mainnet_api_key'
        });
        testnetBtn.classList.remove('active');
        mainnetBtn.classList.add('active');
    }
    if (walletAddress) {
        updateWalletData();
    }
}

// Инициализация
async function init() {
    await initTonConnect();

    // Получаем API ключи из переменных окружения? На GitHub Pages нужно их захардкодить?
    // Для демо используем публичные эндпоинты без ключей (могут быть ограничения)
    // Рекомендуется зарегистрироваться на toncenter.com и получить бесплатный ключ.
    const apiKey = '8f3b3876d5397b086a1e70692334ed235f6aeb0add57669569306b659be321da'; // замените
    client = new TonClient({
        endpoint: isTestnet ? 'https://testnet.toncenter.com/api/v2/jsonRPC' : 'https://toncenter.com/api/v2/jsonRPC',
        apiKey: apiKey
    });

    connectBtn.addEventListener('click', () => tonConnectUI.openModal());
    disconnectBtn.addEventListener('click', () => tonConnectUI.disconnect());
    copyAddressBtn.addEventListener('click', copyAddress);
    sendTonBtn.addEventListener('click', sendTon);
    mainnetBtn.addEventListener('click', () => switchNetwork(false));
    testnetBtn.addEventListener('click', () => switchNetwork(true));
}

init();