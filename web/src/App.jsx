import { useMemo, useState } from "react";

const DEFAULT_SIZE = "1024x1536";

export default function App() {
  const [story, setStory] = useState("");
  const [block, setBlock] = useState("");       // background + 8 prompts (editable)
  const [loadingPrompts, setLoadingPrompts] = useState(false);
  const [loadingZip, setLoadingZip] = useState(false);
  const [useRefs, setUseRefs] = useState(true);
  const [size, setSize] = useState(DEFAULT_SIZE);
  const [panelCount, setPanelCount] = useState(0);

  const countPanels = (text) => {
    const matches = text.match(/\[PROMPT\s*\d+\]/gi);
    return matches ? matches.length : 0;
  };

  const onGeneratePrompts = async () => {
    const trimmed = story.trim();
    if (!trimmed) {
      alert("Please paste a story.");
      return;
    }
    setLoadingPrompts(true);
    try {
      const res = await fetch("/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ story: trimmed })
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || "Failed to generate prompts.");
      }
      const data = await res.json();
      const assembled = renderBlock(data.background, data.panels);
      setBlock(assembled);
      setPanelCount(countPanels(assembled));
    } catch (e) {
      alert(e.message);
    } finally {
      setLoadingPrompts(false);
    }
  };

  const onBlockChange = (val) => {
    setBlock(val);
    setPanelCount(countPanels(val));
  };

  const onGenerateImages = async () => {
    const trimmed = block.trim();
    if (!trimmed) {
      alert("Right panel is empty.");
      return;
    }
    if (panelCount !== 8) {
      if (!confirm(`Detected ${panelCount} prompts. Continue anyway?`)) return;
    }
    setLoadingZip(true);
    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          block: trimmed,
          image: { size },
          useImageReferences: useRefs
        })
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || "Failed to generate images.");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "story_panels.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(e.message);
    } finally {
      setLoadingZip(false);
    }
  };

  return (
    <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:"12px", height:"100%"}}>
      {/* Left: story input */}
      <div style={{display:"flex", flexDirection:"column", padding:"12px"}}>
        <h2 style={{margin:"0 0 8px"}}>Story (any language)</h2>
        <textarea
          style={{flex:1, width:"100%", resize:"none", padding:"8px"}}
          placeholder="Paste or type your story here…"
          value={story}
          onChange={(e)=>setStory(e.target.value)}
        />
        <div style={{display:"flex", gap:"8px", marginTop:"8px"}}>
          <button
            onClick={onGeneratePrompts}
            disabled={!story.trim() || loadingPrompts}
            style={{padding:"8px 12px"}}
          >
            {loadingPrompts ? "Thinking…" : "Generate Background + 8 Prompts"}
          </button>
        </div>
        <p style={{color:"#666", marginTop:"8px"}}>
          Tip: You can edit the right panel’s background and each prompt before generating images.
        </p>
      </div>

      {/* Right: background + prompts editor */}
      <div style={{display:"flex", flexDirection:"column", padding:"12px"}}>
        <h2 style={{margin:"0 0 8px"}}>Background + 8 Prompts (editable)</h2>
        <textarea
          style={{flex:1, width:"100%", resize:"none", padding:"8px"}}
          placeholder={`[BASIC BACKGROUND / CONTEXT]\n...global style, character bible, consistency rules...\n\n[PROMPT 1] Title\n...detailed prompt...\n\n[PROMPT 2] Title\n...`}
          value={block}
          onChange={(e)=>onBlockChange(e.target.value)}
        />
        <div style={{display:"flex", alignItems:"center", gap:"12px", marginTop:"8px"}}>
          <span style={{fontSize:"12px"}}>Detected prompts: {panelCount}</span>
          <label style={{display:"flex", alignItems:"center", gap:"6px"}}>
            <input type="checkbox" checked={useRefs} onChange={(e)=>setUseRefs(e.target.checked)} />
            Use previous images as references
          </label>
          <label style={{display:"flex", alignItems:"center", gap:"6px"}}>
            Size:
            <select value={size} onChange={(e)=>setSize(e.target.value)}>
              <option value="1024x1536">1024x1536 (portrait)</option>
              <option value="1024x1024">1024x1024</option>
              <option value="2048x3072">2048x3072 (portrait, slower)</option>
            </select>
          </label>
          <button
            onClick={onGenerateImages}
            disabled={!block.trim() || loadingZip}
            style={{marginLeft:"auto", padding:"8px 12px"}}
          >
            {loadingZip ? "Generating images…" : "Generate Images (ZIP)"}
          </button>
        </div>
      </div>
    </div>
  );
}

function renderBlock(background, panels) {
  const parts = [];
  parts.push("[BASIC BACKGROUND / CONTEXT]");
  parts.push((background || "").trim());
  parts.push("");

  (panels || []).sort((a,b)=>a.n-b.n).forEach(p=>{
    const title = (p.title || `Panel ${p.n}`).trim();
    const prompt = (p.prompt || "").trim();
    parts.push(`[PROMPT ${p.n}] ${title}`);
    parts.push(prompt);
    parts.push("");
  });

  return parts.join("\n").trim();
}
