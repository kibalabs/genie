const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const escapeHtml = (text) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const LANGUAGE_RULES = {
  yaml: [
    ['comment', /#.*/],
    ['string', /'[^']*'|"[^"]*"/],
    ['key', /(?<=^[ \t]*(?:-[ \t]+)?)[\w-]+(?=:)/m],
    ['type', /\b(?:String|Integer|Float|Boolean|Date|Datetime|Json|Mapping|List|Enum|File|ReadingStatus|true|false)\b/],
    ['number', /\b\d+(?:\.\d+)*\b/],
    ['punct', /[-:[\],]/],
  ],
  python: [
    ['comment', /#.*/],
    ['string', /'[^']*'|"[^"]*"/],
    ['decorator', /@[\w.]+/],
    ['keyword', /\b(?:def|async|await|class|return|import|from|for|in|yield|None|True|False|as|with|if|else|raise)\b/],
    ['type', /\b[A-Z][A-Za-z0-9_]*\b/],
    ['number', /\b\d+\b/],
  ],
  typescript: [
    ['comment', /\/\/.*/],
    ['string', /'[^']*'|`[^`]*`/],
    ['keyword', /\b(?:import|from|export|class|extends|public|async|await|const|return|new|void|undefined)\b/],
    ['type', /\b[A-Z][A-Za-z0-9_]*\b/],
    ['number', /\b\d+\b/],
  ],
  tree: [
    ['comment', /#.*/],
    ['tree', /[├└│─]+/],
  ],
};

const highlight = (code, language) => {
  const rules = LANGUAGE_RULES[language] || [];
  if (rules.length === 0) {
    return escapeHtml(code);
  }
  const pattern = new RegExp(rules.map(([, regex]) => `(${regex.source})`).join('|'), 'gm');
  let output = '';
  let lastIndex = 0;
  for (const match of code.matchAll(pattern)) {
    const ruleIndex = match.slice(1).findIndex((group) => group !== undefined);
    output += escapeHtml(code.slice(lastIndex, match.index));
    output += `<span class="tok-${rules[ruleIndex][0]}">${escapeHtml(match[0])}</span>`;
    lastIndex = match.index + match[0].length;
  }
  return output + escapeHtml(code.slice(lastIndex));
};

const sleep = (milliseconds) => new Promise((resolve) => { setTimeout(resolve, milliseconds); });

const HERO_SPEC = `resources:
  - singleName: Book
    collectionName: Books
    attributes:
      - name: book-id
        type: String
        isPrimary: true
      - name: status
        type: ReadingStatus
    transitions:
      - action: GET`;

const HERO_PYTHON = `class BookshelfApiV1Internal(abc.ABC):

    @abc.abstractmethod
    async def get_book_v1(
        self,
        *,
        bookId: str,
    ) -> resources.BookV1:
        ...`;

const HERO_TYPESCRIPT = `export class BookshelfApiV1Client extends ServiceClient {
  public getBook = async (bookId: string): Promise<Resources.BookV1> => {
    const response = await this.makeRequest(RestMethod.GET, \`books/\${encodeURIComponent(bookId)}\`, undefined, Endpoints.GetBookResponse);
    return response.book;
  };
}`;

const runHero = async () => {
  const specElement = document.getElementById('hero-spec');
  const pythonElement = document.getElementById('hero-python');
  const typescriptElement = document.getElementById('hero-typescript');
  const beam = document.querySelector('.lamp-beam');
  if (prefersReducedMotion) {
    specElement.innerHTML = highlight(HERO_SPEC, 'yaml');
    pythonElement.innerHTML = highlight(HERO_PYTHON, 'python');
    typescriptElement.innerHTML = highlight(HERO_TYPESCRIPT, 'typescript');
    return;
  }
  const revealLines = async (element, code, language) => {
    const lines = code.split('\n');
    for (let lineIndex = 1; lineIndex <= lines.length; lineIndex += 1) {
      element.innerHTML = highlight(lines.slice(0, lineIndex).join('\n'), language);
      await sleep(70);
    }
  };
  for (;;) {
    pythonElement.innerHTML = '';
    typescriptElement.innerHTML = '';
    beam.classList.remove('active');
    for (let index = 1; index <= HERO_SPEC.length; index += 1) {
      specElement.innerHTML = `${highlight(HERO_SPEC.slice(0, index), 'yaml')}<span class="cursor"></span>`;
      await sleep(HERO_SPEC[index - 1] === '\n' ? 90 : 22);
    }
    specElement.innerHTML = highlight(HERO_SPEC, 'yaml');
    beam.classList.add('active');
    await sleep(500);
    await Promise.all([revealLines(pythonElement, HERO_PYTHON, 'python'), revealLines(typescriptElement, HERO_TYPESCRIPT, 'typescript')]);
    await sleep(4200);
  }
};

const setupExplorer = () => {
  const codeElement = document.getElementById('explorer-code');
  const tabs = Array.from(document.querySelectorAll('.tab'));
  const show = (tab) => {
    tabs.forEach((otherTab) => otherTab.setAttribute('aria-selected', String(otherTab === tab)));
    const source = document.getElementById(`file-${tab.dataset.file}`).textContent;
    codeElement.innerHTML = highlight(source, tab.dataset.lang);
    codeElement.style.animation = 'none';
    void codeElement.offsetWidth;
    codeElement.style.animation = '';
    codeElement.scrollTop = 0;
  };
  tabs.forEach((tab) => tab.addEventListener('click', () => show(tab)));
  show(tabs[0]);
};

const setupReveal = () => {
  const elements = document.querySelectorAll('.reveal');
  if (prefersReducedMotion || !('IntersectionObserver' in window)) {
    elements.forEach((element) => element.classList.add('visible'));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  elements.forEach((element, index) => {
    element.style.transitionDelay = `${(index % 4) * 70}ms`;
    observer.observe(element);
  });
};

const setupRouteTable = () => {
  const rows = Array.from(document.querySelectorAll('.route-row:not(.head)'));
  if (prefersReducedMotion || rows.length === 0) {
    return;
  }
  let index = 0;
  setInterval(() => {
    rows.forEach((row) => row.classList.remove('lit'));
    rows[index % rows.length].classList.add('lit');
    index += 1;
  }, 1400);
};

const setupCardGlow = () => {
  document.querySelectorAll('.type-card').forEach((card) => {
    card.addEventListener('pointermove', (event) => {
      const rect = card.getBoundingClientRect();
      card.style.setProperty('--mx', `${event.clientX - rect.left}px`);
      card.style.setProperty('--my', `${event.clientY - rect.top}px`);
    });
  });
};

const setupCopy = () => {
  document.querySelectorAll('.copy').forEach((button) => {
    button.addEventListener('click', async () => {
      const text = document.getElementById(button.dataset.copy).textContent;
      try {
        await navigator.clipboard.writeText(text);
        button.textContent = 'copied';
        button.classList.add('copied');
      } catch {
        button.textContent = 'select it';
      }
      setTimeout(() => {
        button.textContent = 'copy';
        button.classList.remove('copied');
      }, 1600);
    });
  });
};

const WATCH_SCRIPT = [
  ['t-cmd', '$ uvx geniespec watch --spec api.yaml --target python-server -- uvicorn app:app --reload', 900],
  ['t-ok', 'INFO:root:geniespec: built api.yaml into . (7 files changed)', 500],
  ['t-info', 'INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)', 1600],
  ['t-edit', '# api.yaml: add `- action: DELETE` to Book', 1200],
  ['t-ok', 'INFO:root:geniespec: built api.yaml into . (3 files changed)', 400],
  ['t-info', "WARNING:  WatchFiles detected changes in 'bookshelf_api/v1/api.py'. Reloading...", 1600],
  ['t-edit', '# api.yaml: rename book-id to id', 1200],
  ['tok-keyword', 'ERROR:root:geniespec: failed to build api.yaml, keeping the previous output: Primary attribute of Book must be book-id, found id', 1600],
  ['t-edit', '# api.yaml: rename it back', 1000],
  ['t-ok', 'INFO:root:geniespec: built api.yaml into . (0 files changed)', 3200],
];

const runWatchTerminal = async () => {
  const terminal = document.getElementById('watch-terminal');
  const render = (lines) => lines.map(([className, text]) => `<span class="${className}">${escapeHtml(text)}</span>`).join('\n');
  if (prefersReducedMotion) {
    terminal.innerHTML = render(WATCH_SCRIPT);
    return;
  }
  const started = new Promise((resolve) => {
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        observer.disconnect();
        resolve();
      }
    });
    observer.observe(terminal);
  });
  await started;
  for (;;) {
    const shown = [];
    for (const line of WATCH_SCRIPT) {
      shown.push(line);
      terminal.innerHTML = render(shown);
      await sleep(line[2]);
    }
  }
};

const runStars = () => {
  const canvas = document.getElementById('stars');
  const context = canvas.getContext('2d');
  let stars = [];
  const resize = () => {
    const ratio = window.devicePixelRatio || 1;
    canvas.width = window.innerWidth * ratio;
    canvas.height = window.innerHeight * ratio;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    const count = Math.round((window.innerWidth * window.innerHeight) / 9000);
    stars = Array.from({ length: count }, () => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      radius: Math.random() * 1.3 + 0.2,
      speed: Math.random() * 0.15 + 0.03,
      phase: Math.random() * Math.PI * 2,
    }));
  };
  const draw = (time) => {
    context.clearRect(0, 0, window.innerWidth, window.innerHeight);
    stars.forEach((star) => {
      const alpha = 0.35 + 0.45 * Math.sin(time / 900 + star.phase) ** 2;
      context.beginPath();
      context.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
      context.fillStyle = `rgba(214, 200, 255, ${alpha})`;
      context.fill();
      if (!prefersReducedMotion) {
        star.y -= star.speed;
        if (star.y < -2) {
          star.y = window.innerHeight + 2;
          star.x = Math.random() * window.innerWidth;
        }
      }
    });
    if (!prefersReducedMotion) {
      window.requestAnimationFrame(draw);
    }
  };
  resize();
  window.addEventListener('resize', resize);
  window.requestAnimationFrame(draw);
};

runStars();
setupReveal();
setupExplorer();
setupRouteTable();
setupCardGlow();
setupCopy();
runHero();
runWatchTerminal();
