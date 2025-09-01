/************************************************************
 * Markt Dashboard Updater
 * Kopiert aus Tab "Bias":
 *  - A1:F10  → Abschnitt "Dashboard"
 *  - A14:H22 → Abschnitt "Gex Data"
 * und schreibt beides untereinander in das Sheet "Markt Dashboard".
 ************************************************************/

const CONFIG = {
  sourceSheetName: 'Bias',
  targetSheetName: 'Markt Dashboard',
  ranges: [
    { rangeA1: 'A1:F10',  title: 'Dashboard' },
    { rangeA1: 'A14:H22', title: 'Gex Data' }
  ],
  padToCols: 8 // Zielbreite (größter Block hat 8 Spalten: A:H)
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Dashboard')
    .addItem('Markt Dashboard aktualisieren', 'updateMarktDashboard')
    .addToUi();
}

function updateMarktDashboard() {
  const ss   = SpreadsheetApp.getActive();
  const src  = ss.getSheetByName(CONFIG.sourceSheetName);
  if (!src) throw new Error(`Quelle nicht gefunden: ${CONFIG.sourceSheetName}`);

  let dst = ss.getSheetByName(CONFIG.targetSheetName);
  if (!dst) dst = ss.insertSheet(CONFIG.targetSheetName);

  // Daten sammeln & auf gemeinsame Spaltenbreite auffüllen
  const pad = (rows, nCols) =>
    rows.map(r => (r.length < nCols ? r.concat(Array(nCols - r.length).fill('')) : r));

  const all = [];
  const headerRows = []; // für nachträgliche Formatierung (fett)
  let currentRow = 1;

  CONFIG.ranges.forEach((block, idx) => {
    // Abschnittsüberschrift
    const titleRow = [block.title].concat(Array(CONFIG.padToCols - 1).fill(''));
    all.push(titleRow);
    headerRows.push(currentRow);
    currentRow += 1;

    // Blockdaten
    const values = src.getRange(block.rangeA1).getValues();
    const padded = pad(values, CONFIG.padToCols);
    all.push(...padded);
    currentRow += padded.length;

    // Leerzeile zwischen den Abschnitten (außer nach dem letzten)
    if (idx < CONFIG.ranges.length - 1) {
      all.push(Array(CONFIG.padToCols).fill(''));
      currentRow += 1;
    }
  });

  // Zielbereich leeren und neue Daten schreiben
  dst.clearContents();
  dst.getRange(1, 1, all.length, CONFIG.padToCols).setValues(all);

  // Formatierung: Überschriften fett
  headerRows.forEach(r =>
    dst.getRange(r, 1, 1, CONFIG.padToCols).setFontWeight('bold')
  );

  // optional: Spaltenbreite automatisch anpassen
  for (let c = 1; c <= CONFIG.padToCols; c++) dst.autoResizeColumn(c);
}
