/* Helpers every code editor shares (Day 8c).
 *
 *   EditorTools.downloadZip(name, files)
 *       Saves {path: text} as name.zip. Built here in the browser (stored, not
 *       compressed), so it holds what is in the editor right now, saved or not.
 *   EditorTools.keyBar(bar, target)
 *       Wires a row of buttons for the symbols phone keyboards hide. Each button has
 *       data-insert="text" or data-move="-1|1". `target()` returns the active editor:
 *       a CodeMirror instance or a <textarea>.
 */
window.EditorTools = (() => {
  const CRC_TABLE = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      table[n] = c >>> 0;
    }
    return table;
  })();
  const crc32 = (bytes) => {
    let c = 0xffffffff;
    for (const b of bytes) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };

  function zip(files) {
    const encoder = new TextEncoder();
    const now = new Date();
    const time = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1);
    const date = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
    const parts = [], central = [];
    let offset = 0;
    for (const [path, text] of Object.entries(files)) {
      const name = encoder.encode(path), data = encoder.encode(text ?? '');
      const crc = crc32(data);
      const local = new DataView(new ArrayBuffer(30));
      [[0, 0x04034b50, 4], [4, 20, 2], [6, 0x0800, 2], [8, 0, 2], [10, time, 2], [12, date, 2], [14, crc, 4],
        [18, data.length, 4], [22, data.length, 4], [26, name.length, 2], [28, 0, 2]]
        .forEach(([at, value, size]) => (size === 4 ? local.setUint32(at, value, true) : local.setUint16(at, value, true)));
      const entry = new DataView(new ArrayBuffer(46));
      [[0, 0x02014b50, 4], [4, 20, 2], [6, 20, 2], [8, 0x0800, 2], [10, 0, 2], [12, time, 2], [14, date, 2], [16, crc, 4],
        [20, data.length, 4], [24, data.length, 4], [28, name.length, 2], [30, 0, 2], [32, 0, 2], [34, 0, 2], [36, 0, 2],
        [38, 0, 4], [42, offset, 4]]
        .forEach(([at, value, size]) => (size === 4 ? entry.setUint32(at, value, true) : entry.setUint16(at, value, true)));
      parts.push(local, name, data);
      central.push(entry, name);
      offset += 30 + name.length + data.length;
    }
    const size = central.reduce((sum, part) => sum + part.byteLength, 0);
    const end = new DataView(new ArrayBuffer(22));
    const count = Object.keys(files).length;
    [[0, 0x06054b50, 4], [4, 0, 2], [6, 0, 2], [8, count, 2], [10, count, 2], [12, size, 4], [16, offset, 4], [20, 0, 2]]
      .forEach(([at, value, sz]) => (sz === 4 ? end.setUint32(at, value, true) : end.setUint16(at, value, true)));
    return new Blob([...parts, ...central, end], { type: 'application/zip' });
  }

  function downloadZip(name, files) {
    const safe = String(name || 'project').trim().replace(/[^\w؀-ۿ -]+/g, '').replace(/\s+/g, '-').slice(0, 60) || 'project';
    const url = URL.createObjectURL(zip(files));
    const link = Object.assign(document.createElement('a'), { href: url, download: `${safe}.zip` });
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function keyBar(bar, target) {
    if (!bar) return;
    // Keep the editor focused (and the phone keyboard open) when a key is tapped.
    bar.addEventListener('pointerdown', (e) => { if (e.target.closest('button')) e.preventDefault(); });
    bar.addEventListener('click', (e) => {
      const key = e.target.closest('button');
      const ed = key && target();
      if (!ed) return;
      const move = Number(key.dataset.move || 0), text = key.dataset.insert || '';
      if (ed.replaceSelection) {  // CodeMirror
        if (move) ed.execCommand(move < 0 ? 'goCharLeft' : 'goCharRight');
        else ed.replaceSelection(text);
        ed.focus();
      } else {
        if (move) ed.selectionStart = ed.selectionEnd = Math.max(0, ed.selectionStart + move);
        else ed.setRangeText(text, ed.selectionStart, ed.selectionEnd, 'end');
        ed.focus();
        ed.dispatchEvent(new Event('input'));
      }
    });
  }

  return { downloadZip, keyBar, zip };
})();
