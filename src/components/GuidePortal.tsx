import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import {
  Search,
  X,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  Link2,
  BookOpen,
  FileText,
  Clock,
  ArrowUp,
  Sun,
  Moon,
  Maximize2,
  Minimize2,
  AlertTriangle,
  Info,
  List,
  Terminal,
} from "lucide-react";

interface GuideSubsection {
  id: string;
  title: string;
}

type GuideBlock =
  | { type: "paragraph"; text: string }
  | { type: "h3"; id: string; title: string }
  | { type: "code"; lang: string; code: string }
  | { type: "bullet-list"; items: string[] }
  | { type: "numbered-list"; items: { num: string; text: string }[] }
  | { type: "callout"; variant: "important" | "scope" | "note"; title: string; text: string }
  | { type: "hr" };

interface GuideSection {
  id: string;
  num: string;
  rawTitle: string;
  cleanTitle: string;
  subsections: GuideSubsection[];
  blocks: GuideBlock[];
  rawText: string;
}

interface GuideDoc {
  docTitle: string;
  sections: GuideSection[];
  totalTopics: number;
}

/**
 * Parses GUIDE.md while preserving every line of technical content and source code.
 */
function parseGuideMarkdown(rawMd: string): GuideDoc {
  const lines = rawMd.split("\n");
  const sections: GuideSection[] = [];
  let currentSection: GuideSection | null = null;
  let inCodeBlock = false;
  let codeLang = "";
  let codeLines: string[] = [];
  let docTitle = "SnakeCharmers — Project Guide";
  let totalTopics = 0;

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // Check code fence
    if (trimmed.startsWith("```")) {
      if (inCodeBlock) {
        if (currentSection) {
          const codeStr = codeLines.join("\n");
          currentSection.blocks.push({
            type: "code",
            lang: codeLang || "powershell",
            code: codeStr,
          });
          currentSection.rawText += " " + codeStr;
        }
        inCodeBlock = false;
        codeLines = [];
        codeLang = "";
      } else {
        inCodeBlock = true;
        codeLang = trimmed.slice(3).trim();
        codeLines = [];
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(rawLine);
      continue;
    }

    // Heading check (handles optional markdown escaping artifacts like \#, \##, \###)
    const headingMatch = rawLine.match(/^\\?(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const title = headingMatch[2].trim().replace(/[*`]/g, "");

      if (level === 1) {
        docTitle = title;
        continue;
      }

      if (level === 2) {
        totalTopics++;
        const numMatch = title.match(/^(\d+)\.\s*(.+)$/);
        const secNum = numMatch ? numMatch[1].padStart(2, "0") : "";
        const secTitle = numMatch ? numMatch[2] : title;
        const id =
          "section-" +
          (numMatch ? numMatch[1] : sections.length + 1) +
          "-" +
          secTitle.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

        currentSection = {
          id,
          num: secNum,
          rawTitle: title,
          cleanTitle: secTitle,
          subsections: [],
          blocks: [],
          rawText: title,
        };
        sections.push(currentSection);
        continue;
      }

      if (level === 3 && currentSection) {
        totalTopics++;
        const subId =
          currentSection.id +
          "-" +
          title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
        currentSection.subsections.push({
          id: subId,
          title,
        });
        currentSection.blocks.push({
          type: "h3",
          id: subId,
          title,
        });
        currentSection.rawText += " " + title;
        continue;
      }
    }

    // Skip empty lines
    if (!trimmed) {
      continue;
    }

    if (!currentSection) continue;

    // Check Callout Notes
    if (
      trimmed.startsWith("\\*\\*Important:\\*\\*") ||
      trimmed.startsWith("**Important:**")
    ) {
      const text = rawLine
        .replace(/^\\?\*\\?\*Important:\\?\*\\?\*\s*/, "")
        .trim();
      currentSection.blocks.push({
        type: "callout",
        variant: "important",
        title: "Important Limitation",
        text,
      });
      currentSection.rawText += " Important: " + text;
      continue;
    }

    if (
      trimmed.startsWith("\\*\\*Scope note:\\*\\*") ||
      trimmed.startsWith("**Scope note:**")
    ) {
      const text = rawLine
        .replace(/^\\?\*\\?\*Scope note:\\?\*\\?\*\s*/, "")
        .trim();
      currentSection.blocks.push({
        type: "callout",
        variant: "scope",
        title: "Scope Note",
        text,
      });
      currentSection.rawText += " Scope note: " + text;
      continue;
    }

    // Bullet lists
    const bulletMatch = rawLine.match(/^\\?-\s+(.+)$/);
    if (bulletMatch) {
      const itemText = bulletMatch[1];
      const lastBlock = currentSection.blocks[currentSection.blocks.length - 1];
      if (lastBlock && lastBlock.type === "bullet-list") {
        lastBlock.items.push(itemText);
      } else {
        currentSection.blocks.push({
          type: "bullet-list",
          items: [itemText],
        });
      }
      currentSection.rawText += " " + itemText;
      continue;
    }

    // Numbered lists
    const numberedMatch = rawLine.match(/^(\d+)\\?\.\s+(.+)$/);
    if (numberedMatch) {
      const num = numberedMatch[1];
      const text = numberedMatch[2];
      const lastBlock = currentSection.blocks[currentSection.blocks.length - 1];
      if (lastBlock && lastBlock.type === "numbered-list") {
        lastBlock.items.push({ num, text });
      } else {
        currentSection.blocks.push({
          type: "numbered-list",
          items: [{ num, text }],
        });
      }
      currentSection.rawText += " " + text;
      continue;
    }

    // Horizontal divider
    if (trimmed === "\\---" || trimmed === "---") {
      currentSection.blocks.push({ type: "hr" });
      continue;
    }

    // Normal paragraph
    currentSection.blocks.push({
      type: "paragraph",
      text: rawLine,
    });
    currentSection.rawText += " " + rawLine;
  }

  return { docTitle, sections, totalTopics };
}

/**
 * Safely renders inline search highlights without dangerouslySetInnerHTML.
 */
function highlightText(text: string, query: string): React.ReactNode {
  const trimmed = query.trim();
  if (!trimmed) return text;

  const lower = text.toLowerCase();
  const qLower = trimmed.toLowerCase();
  const matchIdx = lower.indexOf(qLower);
  if (matchIdx === -1) return text;

  const result: React.ReactNode[] = [];
  let currentPos = 0;
  let key = 0;

  while (currentPos < text.length) {
    const idx = text.toLowerCase().indexOf(qLower, currentPos);
    if (idx === -1) {
      result.push(text.slice(currentPos));
      break;
    }
    if (idx > currentPos) {
      result.push(text.slice(currentPos, idx));
    }
    result.push(
      <mark key={key++} className="guide-highlight">
        {text.slice(idx, idx + trimmed.length)}
      </mark>
    );
    currentPos = idx + trimmed.length;
  }
  return result;
}

/**
 * Parses inline markdown formatted code (`...`) and bold (**...**) safely.
 */
function renderInlineContent(rawText: string, searchQuery: string): React.ReactNode {
  // Normalize markdown escape characters in prose
  const clean = rawText.replace(/\\([_*\-.#`])/g, "$1");
  const regex = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  const parts = clean.split(regex);

  return parts.map((part, i) => {
    if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
      const codeContent = part.slice(1, -1);
      return (
        <code key={i} className="guide-inline-code">
          {highlightText(codeContent, searchQuery)}
        </code>
      );
    }
    if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
      const boldContent = part.slice(2, -2);
      return (
        <strong key={i} className="guide-bold">
          {highlightText(boldContent, searchQuery)}
        </strong>
      );
    }
    return <span key={i}>{highlightText(part, searchQuery)}</span>;
  });
}

/**
 * Clipboard helper with safe fallback.
 */
function copyToClipboard(text: string, onSuccess: () => void) {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard
      .writeText(text)
      .then(onSuccess)
      .catch(() => fallbackCopy(text, onSuccess));
  } else {
    fallbackCopy(text, onSuccess);
  }
}

function fallbackCopy(text: string, onSuccess: () => void) {
  try {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    document.execCommand("copy");
    document.body.removeChild(textArea);
    onSuccess();
  } catch (err) {
    console.error("Failed to copy:", err);
  }
}

interface GuidePortalProps {
  markdown: string;
}

export default function GuidePortal({ markdown }: GuidePortalProps) {
  // Parsing the document
  const doc = useMemo(() => parseGuideMarkdown(markdown), [markdown]);

  // Reading settings & controls
  const [search, setSearch] = useState("");
  const [density, setDensity] = useState<"comfortable" | "standard" | "compact">("standard");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [activeId, setActiveId] = useState<string>(doc.sections[0]?.id || "");
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});
  const [copiedCodeKey, setCopiedCodeKey] = useState<string | null>(null);
  const [copiedLinkKey, setCopiedLinkKey] = useState<string | null>(null);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [mobileTocOpen, setMobileTocOpen] = useState(false);

  const searchInputRef = useRef<HTMLInputElement>(null);

  // Global Ctrl+K / Cmd+K search shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Reading progress and active section tracker
  const handleScroll = useCallback(() => {
    const scrollY = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress =
      docHeight > 0
        ? Math.min(100, Math.max(0, Math.round((scrollY / docHeight) * 100)))
        : 0;

    setScrollProgress(progress);
    setShowBackToTop(scrollY > 320);

    // Track active section based on scroll position
    const sectionElements = doc.sections.map((s) => ({
      id: s.id,
      el: document.getElementById(s.id),
    }));

    for (let i = sectionElements.length - 1; i >= 0; i--) {
      const item = sectionElements[i];
      if (item.el) {
        const rect = item.el.getBoundingClientRect();
        if (rect.top <= 140) {
          setActiveId(item.id);
          break;
        }
      }
    }
  }, [doc.sections]);

  useEffect(() => {
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  // Jump to URL hash on initial load if present
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (hash) {
      setTimeout(() => {
        const el = document.getElementById(hash);
        if (el) {
          el.scrollIntoView({ behavior: "smooth" });
          setActiveId(hash);
        }
      }, 150);
    }
  }, []);

  // Filter sections by search query
  const filteredSections = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return doc.sections;

    return doc.sections.filter(
      (sec) =>
        sec.cleanTitle.toLowerCase().includes(q) ||
        sec.rawText.toLowerCase().includes(q)
    );
  }, [doc.sections, search]);

  // Section toggle helpers
  const toggleSection = (id: string) => {
    setCollapsedSections((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const expandAll = () => setCollapsedSections({});
  const collapseAll = () => {
    const all: Record<string, boolean> = {};
    doc.sections.forEach((s) => {
      all[s.id] = true;
    });
    setCollapsedSections(all);
  };

  const scrollToId = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
      setActiveId(id);
      window.history.replaceState(null, "", `#${id}`);
      setMobileTocOpen(false);
    }
  };

  const handleCopyHeadingLink = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const url = window.location.origin + window.location.pathname + `#${id}`;
    copyToClipboard(url, () => {
      setCopiedLinkKey(id);
      setTimeout(() => setCopiedLinkKey(null), 2000);
    });
  };

  const handleCopyCode = (code: string, key: string) => {
    copyToClipboard(code, () => {
      setCopiedCodeKey(key);
      setTimeout(() => setCopiedCodeKey(null), 2000);
    });
  };

  const activeSectionTitle = useMemo(() => {
    const sec = doc.sections.find((s) => s.id === activeId);
    return sec ? sec.cleanTitle : doc.sections[0]?.cleanTitle || "Documentation";
  }, [doc.sections, activeId]);

  return (
    <div className={`guide-portal theme-${theme} density-${density}`}>
      {/* Reading Progress Indicator */}
      <div className="guide-progress-bar-wrap" title={`Reading Progress: ${scrollProgress}%`}>
        <div
          className="guide-progress-bar-fill"
          style={{ width: `${scrollProgress}%` }}
        />
      </div>

      <div className="page-content" style={{ maxWidth: 1400, margin: "0 auto", padding: "1.5rem" }}>
        {/* Refined Documentation Header Banner */}
        <header className="guide-hero">
          <div className="guide-hero-badge">
            <BookOpen size={13} />
            <span>Developer Documentation Portal</span>
          </div>

          <h1 className="guide-hero-title">
            SnakeCharmers <span style={{ color: "var(--g-cyan)" }}>// Project Guide</span>
          </h1>

          <p className="guide-hero-desc">
            Complete technical reference for the warehouse slotting optimization pipeline,
            synthetic layout topology, Olist data constraints, and simulation validation.
          </p>

          <div className="guide-hero-meta">
            <div className="guide-meta-chip">
              <span className="guide-meta-label">SOURCE SPEC</span>
              <span className="guide-meta-value">GUIDE.md</span>
            </div>
            <div className="guide-meta-chip">
              <span className="guide-meta-label">ARCHITECTURE</span>
              <span className="guide-meta-value">RESEARCH PROTOTYPE</span>
            </div>
            <div className="guide-meta-chip">
              <span className="guide-meta-label">DOCUMENTATION MODULES</span>
              <span className="guide-meta-value">
                {doc.sections.length} SECTIONS • {doc.totalTopics} TOPICS
              </span>
            </div>
            <div className="guide-meta-chip">
              <span className="guide-meta-label">EST. READ TIME</span>
              <span className="guide-meta-value">~10 MIN</span>
            </div>
          </div>
        </header>

        {/* Sticky Interactive Toolbar */}
        <div className="guide-toolbar">
          {/* Live Search */}
          <div className="guide-search-box">
            <Search size={15} className="guide-search-icon" />
            <input
              ref={searchInputRef}
              type="text"
              className="guide-search-input"
              placeholder="Search documentation (e.g. Olist, pipeline, heuristic)..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search guide content"
            />
            <div className="guide-search-right">
              {search ? (
                <button
                  className="guide-clear-search"
                  onClick={() => {
                    setSearch("");
                    searchInputRef.current?.focus();
                  }}
                  title="Clear search"
                  aria-label="Clear search"
                >
                  <X size={14} />
                </button>
              ) : (
                <span className="guide-kbd">Ctrl+K</span>
              )}
            </div>
          </div>

          {/* Controls: Density, Theme, Expand/Collapse */}
          <div className="guide-actions-row">
            {/* Density Selector */}
            <div className="guide-segmented" title="Reading Density">
              <button
                className={`guide-segment-btn ${density === "comfortable" ? "active" : ""}`}
                onClick={() => setDensity("comfortable")}
                title="Comfortable Density"
              >
                Comfort
              </button>
              <button
                className={`guide-segment-btn ${density === "standard" ? "active" : ""}`}
                onClick={() => setDensity("standard")}
                title="Standard Density"
              >
                Standard
              </button>
              <button
                className={`guide-segment-btn ${density === "compact" ? "active" : ""}`}
                onClick={() => setDensity("compact")}
                title="Compact Density"
              >
                Compact
              </button>
            </div>

            {/* Expand / Collapse All */}
            <button
              className="guide-tool-btn"
              onClick={Object.keys(collapsedSections).length > 0 ? expandAll : collapseAll}
              title={Object.keys(collapsedSections).length > 0 ? "Expand all sections" : "Collapse all sections"}
            >
              {Object.keys(collapsedSections).length > 0 ? (
                <>
                  <Maximize2 size={13} />
                  <span>Expand All</span>
                </>
              ) : (
                <>
                  <Minimize2 size={13} />
                  <span>Collapse All</span>
                </>
              )}
            </button>

            {/* Theme Toggle (Dark / Light) */}
            <button
              className="guide-tool-btn"
              onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
              title={`Switch to ${theme === "dark" ? "Light" : "Dark"} mode`}
              aria-label="Toggle Theme"
            >
              {theme === "dark" ? <Sun size={13} /> : <Moon size={13} />}
              <span>{theme === "dark" ? "Light" : "Dark"}</span>
            </button>

            {/* Mobile TOC Button */}
            <button
              className="guide-tool-btn guide-mobile-toc-btn"
              onClick={() => setMobileTocOpen((o) => !o)}
              title="Table of Contents"
            >
              <List size={13} />
              <span>Contents</span>
            </button>
          </div>
        </div>

        {/* Mobile TOC Drawer */}
        {mobileTocOpen && (
          <div className="guide-mobile-toc-drawer">
            <div className="guide-toc-head">
              <span className="guide-toc-title">TABLE OF CONTENTS</span>
              <button
                className="guide-icon-btn"
                onClick={() => setMobileTocOpen(false)}
                aria-label="Close contents"
              >
                <X size={14} />
              </button>
            </div>
            <nav className="guide-toc-nav">
              {doc.sections.map((sec) => (
                <div key={sec.id}>
                  <a
                    href={`#${sec.id}`}
                    className={`guide-toc-link ${activeId === sec.id ? "active" : ""}`}
                    onClick={(e) => {
                      e.preventDefault();
                      scrollToId(sec.id);
                    }}
                  >
                    <span className="guide-toc-num">{sec.num}</span>
                    <span>{sec.cleanTitle}</span>
                  </a>
                </div>
              ))}
            </nav>
          </div>
        )}

        {/* Main Documentation Layout */}
        <div className="guide-layout">
          {/* Main Reading Content Area */}
          <main className="guide-content-area">
            {filteredSections.length === 0 ? (
              <div className="guide-empty-search">
                <Search size={32} className="guide-empty-icon" />
                <h3 className="guide-empty-title">No documentation matches found</h3>
                <p className="guide-empty-desc">
                  We couldn't find any sections matching &quot;{search}&quot;. Try searching for
                  pipeline commands, warehouse config, or heuristic solver assumptions.
                </p>
                <button
                  className="guide-tool-btn"
                  onClick={() => setSearch("")}
                >
                  <X size={13} />
                  <span>Clear Search Filter</span>
                </button>
              </div>
            ) : (
              filteredSections.map((sec) => {
                const isCollapsed = Boolean(collapsedSections[sec.id]);

                return (
                  <article
                    key={sec.id}
                    id={sec.id}
                    className={`guide-section ${activeId === sec.id ? "active-reading" : ""}`}
                  >
                    {/* Major Section Header */}
                    <div
                      className="guide-section-header"
                      onClick={() => toggleSection(sec.id)}
                      role="button"
                      tabIndex={0}
                      aria-expanded={!isCollapsed}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          toggleSection(sec.id);
                        }
                      }}
                    >
                      <div className="guide-section-title-wrap">
                        <span className="guide-section-num">{sec.num || "•"}</span>
                        <h2 className="guide-section-h2">
                          {highlightText(sec.cleanTitle, search)}
                        </h2>
                      </div>

                      <div className="guide-section-actions">
                        {/* Copy Link to Section */}
                        <button
                          className="guide-icon-btn"
                          onClick={(e) => handleCopyHeadingLink(sec.id, e)}
                          title="Copy link to this section"
                          aria-label={`Copy link to section ${sec.cleanTitle}`}
                        >
                          {copiedLinkKey === sec.id ? (
                            <Check size={14} style={{ color: "var(--g-cyan)" }} />
                          ) : (
                            <Link2 size={14} />
                          )}
                        </button>

                        {/* Expand / Collapse Chevron */}
                        <button
                          className="guide-icon-btn"
                          aria-label={isCollapsed ? "Expand section" : "Collapse section"}
                        >
                          {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                        </button>
                      </div>
                    </div>

                    {/* Section Body */}
                    {!isCollapsed && (
                      <div className="guide-section-body">
                        {sec.blocks.map((block, bIdx) => {
                          if (block.type === "h3") {
                            return (
                              <div
                                key={bIdx}
                                id={block.id}
                                className="guide-h3-wrap"
                              >
                                <h3 className="guide-h3">
                                  {highlightText(block.title, search)}
                                </h3>
                                <button
                                  className="guide-icon-btn"
                                  onClick={(e) => handleCopyHeadingLink(block.id, e)}
                                  title="Copy link to subsection"
                                  aria-label={`Copy link to ${block.title}`}
                                >
                                  {copiedLinkKey === block.id ? (
                                    <Check size={12} style={{ color: "var(--g-cyan)" }} />
                                  ) : (
                                    <Link2 size={12} />
                                  )}
                                </button>
                              </div>
                            );
                          }

                          if (block.type === "code") {
                            const codeKey = `${sec.id}-code-${bIdx}`;
                            const isCopied = copiedCodeKey === codeKey;

                            return (
                              <div key={bIdx} className="guide-code-card">
                                <div className="guide-code-header">
                                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                                    <Terminal size={12} style={{ color: "var(--g-cyan)" }} />
                                    <span className="guide-code-lang">{block.lang}</span>
                                  </div>
                                  <button
                                    className="guide-copy-btn"
                                    onClick={() => handleCopyCode(block.code, codeKey)}
                                    title="Copy code snippet"
                                  >
                                    {isCopied ? (
                                      <>
                                        <Check size={12} style={{ color: "var(--g-cyan)" }} />
                                        <span style={{ color: "var(--g-cyan)" }}>Copied!</span>
                                      </>
                                    ) : (
                                      <>
                                        <Copy size={12} />
                                        <span>Copy</span>
                                      </>
                                    )}
                                  </button>
                                </div>
                                <pre className="guide-code-pre">
                                  <code>{block.code}</code>
                                </pre>
                              </div>
                            );
                          }

                          if (block.type === "callout") {
                            const isImportant = block.variant === "important";
                            return (
                              <div
                                key={bIdx}
                                className={`guide-callout ${
                                  isImportant ? "callout-important" : "callout-note"
                                }`}
                              >
                                <div className="guide-callout-icon">
                                  {isImportant ? (
                                    <AlertTriangle size={18} />
                                  ) : (
                                    <Info size={18} />
                                  )}
                                </div>
                                <div className="guide-callout-body">
                                  <div className="guide-callout-title">{block.title}</div>
                                  <div>{renderInlineContent(block.text, search)}</div>
                                </div>
                              </div>
                            );
                          }

                          if (block.type === "bullet-list") {
                            return (
                              <ul key={bIdx} className="guide-bullet-list">
                                {block.items.map((item, itIdx) => (
                                  <li key={itIdx} className="guide-bullet-item">
                                    {renderInlineContent(item, search)}
                                  </li>
                                ))}
                              </ul>
                            );
                          }

                          if (block.type === "numbered-list") {
                            return (
                              <ol key={bIdx} className="guide-numbered-list">
                                {block.items.map((item, itIdx) => (
                                  <li key={itIdx} className="guide-numbered-item">
                                    <span className="guide-num-badge">{item.num}</span>
                                    <span>{renderInlineContent(item.text, search)}</span>
                                  </li>
                                ))}
                              </ol>
                            );
                          }

                          if (block.type === "hr") {
                            return <hr key={bIdx} className="guide-hr" />;
                          }

                          // Standard paragraph
                          return (
                            <p key={bIdx}>
                              {renderInlineContent(block.text, search)}
                            </p>
                          );
                        })}
                      </div>
                    )}
                  </article>
                );
              })
            )}
          </main>

          {/* Sticky Table of Contents (Desktop Sidebar) */}
          <aside className="guide-toc-sidebar" aria-label="Table of contents">
            <div className="guide-toc-head">
              <span className="guide-toc-title">IN THIS GUIDE</span>
              <span className="guide-toc-progress">{scrollProgress}%</span>
            </div>

            <nav className="guide-toc-nav">
              {doc.sections.map((sec) => (
                <div key={sec.id}>
                  <a
                    href={`#${sec.id}`}
                    className={`guide-toc-link ${activeId === sec.id ? "active" : ""}`}
                    onClick={(e) => {
                      e.preventDefault();
                      scrollToId(sec.id);
                    }}
                  >
                    <span className="guide-toc-num">{sec.num}</span>
                    <span>{sec.cleanTitle}</span>
                  </a>

                  {/* Nested Subsections */}
                  {sec.subsections.length > 0 && (
                    <div style={{ paddingLeft: "0.25rem", marginTop: "0.1rem", marginBottom: "0.3rem" }}>
                      {sec.subsections.map((sub) => (
                        <a
                          key={sub.id}
                          href={`#${sub.id}`}
                          className={`guide-toc-link is-sub ${activeId === sub.id ? "active" : ""}`}
                          onClick={(e) => {
                            e.preventDefault();
                            scrollToId(sub.id);
                          }}
                        >
                          <span>{sub.title}</span>
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </nav>
          </aside>
        </div>

        {/* Floating Back to Top Button */}
        {showBackToTop && (
          <button
            className="guide-back-to-top"
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            title="Back to top"
            aria-label="Scroll back to top"
          >
            <ArrowUp size={14} />
            <span>Top</span>
          </button>
        )}
      </div>
    </div>
  );
}
