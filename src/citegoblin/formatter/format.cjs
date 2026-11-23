// CSL formatting only. No network, Google, browser, or Zotero calls.
const fs=require('node:fs'),path=require('node:path');
const CSL=require('citeproc');
const registry=JSON.parse(fs.readFileSync(0,'utf8'));
if(typeof registry.styleXml!=='string')throw Error('Validated CSL style XML is required');
const sys={retrieveLocale:lang=>{if(!/^en(?:-|$)/i.test(lang))throw Error('Locale not bundled: '+lang);return fs.readFileSync(path.join(__dirname,lang==='en-US'?'locales-en-US.xml':'locales-en-GB.xml'),'utf8');},retrieveItem:id=>{
 const item=registry.records[id]?.csl;if(!item)throw Error('Missing reference '+id);return item;
}};
const engine=new CSL.Engine(sys,registry.styleXml,registry.locale||'en-GB');
engine.setOutputFormat('text');
const clusters=registry.citations.map(c=>({citationID:c.id,citationItems:c.items,properties:{noteIndex:0}}));
const cited=new Set(clusters.flatMap(c=>c.citationItems.map(i=>i.id)));
const retained=[...new Set([...(registry.bibliography.currentOrder||[]),...Object.keys(registry.records)])].filter(id=>!cited.has(id));
const updates=engine.rebuildProcessorState(clusters,'text',retained);
const bibliography=engine.makeBibliography();if(!bibliography)throw Error('Style has no bibliography');
const [info,entries]=bibliography;const order=info.entry_ids.map(ids=>ids[0]);
if(order.length!==Object.keys(registry.records).length || new Set(order).size!==order.length)throw Error('Bibliography coverage failure');
engine.setOutputFormat('html');
const htmlUpdates=engine.rebuildProcessorState(clusters,'html',retained);
const htmlBibliography=engine.makeBibliography();
process.stdout.write(JSON.stringify({style:registry.style,citations:updates.map(([id,note,text])=>({id,text})),bibliography:entries.join('').trimEnd(),order,citationHtml:Object.fromEntries(htmlUpdates.map(([id,note,html])=>[id,html])),bibliographyHtml:htmlBibliography[1].join('')}));
