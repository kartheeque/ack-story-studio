import { useEffect, useMemo, useState } from "react";

const DEFAULT_SIZE = "1024x1536";

export default function App() {
  const [story, setStory] = useState("");
  const [block, setBlock] = useState("");       // background + prompts (editable)
  const [loadingPrompts, setLoadingPrompts] = useState(false);
  const [useRefs, setUseRefs] = useState(true);
  const [size, setSize] = useState(DEFAULT_SIZE);
  const [currentPanelPosition, setCurrentPanelPosition] = useState(1);
  const [generatingImage, setGeneratingImage] = useState(false);
  const [previousImageBase64, setPreviousImageBase64] = useState(null);

  const { panels } = useMemo(() => parseBlock(block), [block]);
  const totalPanels = panels.length;
  const nextPanel = panels[currentPanelPosition - 1] || null;

  useEffect(() => {
    if (currentPanelPosition > totalPanels + 1) {
      setCurrentPanelPosition(totalPanels === 0 ? 1 : totalPanels + 1);
    }
  }, [currentPanelPosition, totalPanels]);

  useEffect(() => {
    if (!useRefs) {
      setPreviousImageBase64(null);
    }
  }, [useRefs]);

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
      setCurrentPanelPosition(1);
      setPreviousImageBase64(null);
    } catch (e) {
      alert(e.message);
    } finally {
      setLoadingPrompts(false);
    }
  };

  const onBlockChange = (val) => {
    setBlock(val);
  };

  const onGenerateNextImage = async () => {
    const trimmed = block.trim();
    if (!trimmed) {
      alert("Right panel is empty.");
      return;
    }
    if (!nextPanel) {
      alert("All prompts have been generated.");
      return;
    }
    if (currentPanelPosition === 1 && totalPanels !== 8) {
      if (!confirm(`Detected ${totalPanels} prompts. Continue anyway?`)) return;
    }
    setGeneratingImage(true);
    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          block: trimmed,
          image: { size },
          useImageReferences: useRefs,
          panelIndex: currentPanelPosition,
          previousImage: useRefs ? previousImageBase64 : null
        })
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || "Failed to generate images.");
      }
      const data = await res.json();
      if (!data.imageBase64) {
        throw new Error("Image payload missing from response.");
      }
      const filename = data.filename || `panel-${String(currentPanelPosition).padStart(2, "0")}.png`;
      const byteCharacters = atob(data.imageBase64);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i += 1) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: "image/png" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setPreviousImageBase64(data.imageBase64);
      setCurrentPanelPosition((prev) => prev + 1);
    } catch (e) {
      alert(e.message);
    } finally {
      setGeneratingImage(false);
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
          <span style={{fontSize:"12px"}}>Detected prompts: {totalPanels}</span>
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
            onClick={onGenerateNextImage}
            disabled={!block.trim() || generatingImage || !nextPanel}
            style={{marginLeft:"auto", padding:"8px 12px"}}
          >
            {generatingImage
              ? (nextPanel ? `Generating [PROMPT ${nextPanel.n}] ${nextPanel.title}…` : "Generating image…")
              : (nextPanel ? `Generate [PROMPT ${nextPanel.n}] ${nextPanel.title}` : "All images generated")}
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

function parseBlock(text) {
  const lines = text.split(/\r?\n/);
  const indices = [];
  lines.forEach((line, idx) => {
    const match = line.trim().match(/^\[PROMPT\s*(\d{1,2})\]\s*(.*)$/i);
    if (match) {
      indices.push({ index: idx, n: parseInt(match[1], 10), title: (match[2] || "").trim() });
    }
  });

  if (indices.length === 0) {
    return { background: text.trim(), panels: [] };
  }

  const firstIdx = indices[0].index;
  const background = lines.slice(0, firstIdx).join("\n").trim();

  const panels = indices.map((entry, idx) => {
    const nextLine = idx + 1 < indices.length ? indices[idx + 1].index : lines.length;
    const body = lines.slice(entry.index + 1, nextLine).join("\n").trim();
    const title = entry.title || `Panel ${entry.n}`;
    return { n: entry.n, title, prompt: body };
  });

  panels.sort((a, b) => a.n - b.n);

  return { background, panels };
}
