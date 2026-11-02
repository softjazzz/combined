// 首页V2定向前端验收：从Node传输层禁止真实TCP/TLS/fetch，不允许误接运行中的后端。
const net = require('node:net');
const tls = require('node:tls');
const deny = () => { throw new Error('Frontpage V2 isolated tests prohibit real network'); };
net.Socket.prototype.connect = deny;
net.connect = deny;
net.createConnection = deny;
tls.connect = deny;
globalThis.fetch = deny;
