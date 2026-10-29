
import {
  ArrowRight,
  Boxes,
  ChartNoAxesCombined,
  MapPinned,
  ScanLine,
  Activity,
  Route,
} from "lucide-react";


type HomeProps = {
  onEnterDashboard: () => void;
};

const steps = [
  {
    number: "01",
    icon: ChartNoAxesCombined,
    title: "Understand demand",
    description:
      "Identify which products move frequently and which inventory needs a closer look.",
  },
  {
    number: "02",
    icon: Boxes,
    title: "Discover affinity",
    description:
      "Find products that frequently appear together in customer orders.",
  },
  {
    number: "03",
    icon: ScanLine,
    title: "Optimize slotting",
    description:
      "Place inventory strategically, considering demand, product relationships, and warehouse constraints.",
  },
  {
    number: "04",
    icon: MapPinned,
    title: "Improve picking",
    description:
      "Evaluate picking routes and compare the optimized plan with a baseline.",
  },
];

function WarehouseScene() {
  return (
    <div
      className="home-warehouse"
      role="img"
      aria-label="Animated forklift moving through warehouse racks and scanning inventory"
    >
      <div className="home-scene-label">
        <span>WAREHOUSE SIMULATION</span>
        <span className="home-scene-live">
          <i /> SCANNING INVENTORY
        </span>
      </div>

      <div className="home-warehouse-grid" />
      
<div className="home-rack-highlights" aria-hidden="true">
  <span className="home-rack-highlight home-rack-highlight-1" />
  <span className="home-rack-highlight home-rack-highlight-2" />
  <span className="home-rack-highlight home-rack-highlight-3" />
  <span className="home-rack-highlight home-rack-highlight-4" />
</div>


      <svg
        className="home-scene-svg"
        viewBox="0 0 760 310"
        preserveAspectRatio="xMidYMid meet"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="rackGlow" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#163c48" />
            <stop offset="100%" stopColor="#0b1921" />
          </linearGradient>
          <linearGradient id="forkliftBody" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ffc96b" />
            <stop offset="100%" stopColor="#c98127" />
          </linearGradient>
          <pattern
            id="rackSlots"
            width="64"
            height="49"
            patternUnits="userSpaceOnUse"
          >
            <rect
              x="4"
              y="5"
              width="54"
              height="36"
              rx="2"
              fill="#102832"
              stroke="#28515b"
              strokeWidth="1"
            />
            <path d="M10 12H51" stroke="#315b65" strokeWidth="2" />
            <rect x="11" y="18" width="12" height="15" fill="#1c6968" />
            <rect x="26" y="18" width="12" height="15" fill="#24518a" />
            <rect x="41" y="18" width="10" height="15" fill="#b77c31" />
          </pattern>
        </defs>

        <g opacity="0.95">
          <rect
            x="30"
            y="28"
            width="210"
            height="195"
            fill="url(#rackGlow)"
            stroke="#28515b"
          />
          <rect x="30" y="28" width="210" height="195" fill="url(#rackSlots)" />
          <path d="M30 28V223M240 28V223" stroke="#36717b" strokeWidth="4" />
          <path d="M30 77H240M30 126H240M30 175H240" stroke="#36717b" strokeWidth="3" />

          <rect
            x="520"
            y="28"
            width="210"
            height="195"
            fill="url(#rackGlow)"
            stroke="#28515b"
          />
          <rect x="520" y="28" width="210" height="195" fill="url(#rackSlots)" />
          <path d="M520 28V223M730 28V223" stroke="#36717b" strokeWidth="4" />
          <path d="M520 77H730M520 126H730M520 175H730" stroke="#36717b" strokeWidth="3" />
        </g>

        <path d="M260 223H500L600 304H160Z" fill="#0b161d" />
        <path
          d="M275 225L225 304M485 225L535 304"
          stroke="#21434d"
          strokeWidth="2"
          strokeDasharray="8 9"
        />
        <path
          d="M380 235V302"
          stroke="#25f4d0"
          strokeWidth="1"
          strokeDasharray="5 9"
          opacity="0.5"
        />

        <g className="home-forklift">
          <ellipse cx="15" cy="238" rx="65" ry="8" fill="#000" opacity="0.45" />

          <g className="home-forklift-scan">
            <path d="M-35 112L-180 20V180Z" fill="#25f4d0" opacity="0.08" />
            <path
              d="M-35 112L-180 20M-35 112L-180 180"
              stroke="#25f4d0"
              strokeWidth="1.5"
              opacity="0.65"
            />
            <path
              d="M-145 35V165"
              stroke="#25f4d0"
              strokeWidth="2"
              strokeDasharray="4 5"
            />
          </g>

          <g transform="translate(-38 0)">
            <circle cx="0" cy="222" r="14" fill="#071016" stroke="#57727b" strokeWidth="4" />
            <circle cx="0" cy="222" r="5" fill="#8ba2ab" />
            <circle cx="68" cy="222" r="14" fill="#071016" stroke="#57727b" strokeWidth="4" />
            <circle cx="68" cy="222" r="5" fill="#8ba2ab" />

            <path d="M-23 207V157H19L36 187H87V211H-23Z" fill="url(#forkliftBody)" />
            <path d="M-12 161H12L28 184H-12Z" fill="#10212a" />
            <path d="M19 157L32 184H49L39 157Z" fill="#eaa33e" />
            <path d="M43 186H83V202H43Z" fill="#d89332" />

            <path
              d="M43 157V102H56V184"
              fill="none"
              stroke="#a7bdc4"
              strokeWidth="6"
            />
            <path d="M42 101H66" stroke="#d4e3e8" strokeWidth="5" />
            <path d="M44 180H89V185H44Z" fill="#dce9ee" />
            <path d="M-18 190H-8" stroke="#25f4d0" strokeWidth="3" />
          </g>

          <g className="home-forklift-pallet">
            <rect x="15" y="119" width="36" height="28" fill="#24518a" stroke="#4b8cff" />
            <rect x="53" y="119" width="30" height="28" fill="#1c6968" stroke="#25f4d0" />
            <path d="M12 151H87" stroke="#b9cbd1" strokeWidth="4" />
            <path d="M20 156H80" stroke="#829ca5" strokeWidth="2" />
          </g>
        </g>

        <g className="home-scan-marker">
          <rect x="563" y="90" width="116" height="42" rx="3" fill="#07151b" stroke="#25f4d0" />
          <path d="M576 103H604M576 110H598M576 117H608" stroke="#25f4d0" strokeWidth="2" />
          <text x="615" y="109" fill="#b4fff4" fontSize="8" fontFamily="monospace">SKU SCAN</text>
          <text x="615" y="120" fill="#6ca5a6" fontSize="7" fontFamily="monospace">IN PROGRESS</text>
        </g>
      </svg>

      <div className="home-scene-footer">
        <span>01 / INSPECT</span>
        <span>02 / SCAN</span>
        <span>03 / CONTINUE</span>
      </div>
    </div>
  );
}

export default function Home({ onEnterDashboard }: HomeProps) {
  return (
    <main className="home-page">
      <nav className="home-nav">
        <a className="home-brand" href="#home" aria-label="SnakeCharmers home">
          <span className="home-brand-mark">SC</span>
          <span>
            <strong>SNAKECHARMERS</strong>
            <small>WAREHOUSE INTELLIGENCE</small>
          </span>
        </a>

        <div className="home-nav-links">
          <a href="#how-it-works">HOW IT WORKS</a>
          <button className="home-nav-cta" onClick={onEnterDashboard}>
            OPEN DASHBOARD <ArrowRight size={15} />
          </button>
        </div>
      </nav>

      <section className="home-hero" id="home">
        <div className="home-hero-copy">
          <div className="home-eyebrow">
            <span /> INTELLIGENT WAREHOUSE OPTIMIZATION
          </div>

          <h1>
            Smarter Slotting.
            <br />
            <span>Faster Fulfilment.</span>
          </h1>

          <p>
            Turn order history into smarter inventory placement and more
            efficient picking decisions.
          </p>

          <div className="home-hero-actions">
            <button className="home-primary-cta" onClick={onEnterDashboard}>
              ENTER DASHBOARD <ArrowRight size={17} />
            </button>
            <a className="home-secondary-cta" href="#how-it-works">
              EXPLORE THE SYSTEM <span>↓</span>
            </a>
          </div>

          <div className="home-proof">
            <span className="home-proof-icon"><ScanLine size={16} /></span>
            <span>
              <strong>DATA-DRIVEN DECISIONS</strong>
              <small>Demand · Affinity · Slotting · Routing</small>
            </span>
          </div>
        </div>

        <WarehouseScene />
      </section>
    
      <section className="home-intelligence" aria-label="Warehouse intelligence capabilities">
        <div className="home-intelligence-heading">
          <span className="home-intelligence-pulse" />
          SYSTEM CAPABILITIES
        </div>

        <div className="home-intelligence-grid">
          <article className="home-intelligence-item">
            <span className="home-intelligence-icon">
              <Activity size={19} />
            </span>
            <div>
              <h3>DEMAND INTELLIGENCE</h3>
              <p>Identify fast-moving products from order history.</p>
            </div>
            <span className="home-intelligence-index">01</span>
          </article>

          <article className="home-intelligence-item">
            <span className="home-intelligence-icon">
              <Boxes size={19} />
            </span>
            <div>
              <h3>PRODUCT AFFINITY</h3>
              <p>Discover products frequently ordered together.</p>
            </div>
            <span className="home-intelligence-index">02</span>
          </article>

          <article className="home-intelligence-item">
            <span className="home-intelligence-icon">
              <Route size={19} />
            </span>
            <div>
              <h3>ROUTE OPTIMIZATION</h3>
              <p>Evaluate picking routes against a baseline.</p>
            </div>
            <span className="home-intelligence-index">03</span>
          </article>
        </div>
      </section>

      <section className="home-process" id="how-it-works">
        <div className="home-section-heading">
          <div>
            <div className="home-eyebrow">THE OPTIMIZATION PIPELINE</div>
            <h2>From order history to better decisions.</h2>
          </div>
          <p>
            A connected workflow for understanding demand, organizing
            inventory, and evaluating warehouse operations.
          </p>
        </div>

        <div className="home-steps">
          {steps.map(({ number, icon: Icon, title, description }) => (
            <article className="home-step" key={number}>
              <div className="home-step-top">
                <span>{number} / 04</span>
                <Icon size={19} />
              </div>
              <h3>{title}</h3>
              <p>{description}</p>
              <div className="home-step-line" />
            </article>
          ))}
        </div>
      </section>

      <footer className="home-footer">
        <span>SNAKECHARMERS <i> / </i> SMART WAREHOUSE SYSTEM</span>
        <button onClick={onEnterDashboard}>
          OPEN THE DASHBOARD <ArrowRight size={14} />
        </button>
      </footer>
    </main>
  );
}
