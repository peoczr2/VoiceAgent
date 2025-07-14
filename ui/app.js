const { useState, useRef, useEffect } = React;

function reorder(tabs, sourceId, targetId) {
  const srcIndex = tabs.findIndex(t => t.id === sourceId);
  const tgtIndex = tabs.findIndex(t => t.id === targetId);
  if (srcIndex === -1 || tgtIndex === -1) return tabs;
  const updated = [...tabs];
  const [moved] = updated.splice(srcIndex, 1);
  updated.splice(tgtIndex, 0, moved);
  return updated;
}

let nextTabId = 1;

function BrowserApp() {
  const params = new URLSearchParams(window.location.search);
  const initialUrl = params.get('url') || '';
  const initialTitle = params.get('title') || 'New Tab';
  const [tabs, setTabs] = useState([
    { id: nextTabId++, url: initialUrl, title: initialTitle }
  ]);
  const [activeTabId, setActiveTabId] = useState(tabs[0].id);
  const dragTab = useRef(null);
  const stripRef = useRef(null);
  const iframeRef = useRef(null);

  const activeTab = tabs.find(t => t.id === activeTabId);

  function addNewTab() {
    const newTab = { id: nextTabId++, url: '', title: 'New Tab' };
    setTabs([...tabs, newTab]);
    setActiveTabId(newTab.id);
  }

  function loadUrl(url) {
    setTabs(tabs.map(t => t.id === activeTabId ? { ...t, url, title: url } : t));
  }

  async function detachTab(id) {
    const tab = tabs.find(t => t.id === id);
    if (!tab) return;
    if (window.pywebview) {
      await window.pywebview.api.popout_tab(tab.url, tab.title);
    }
    const remaining = tabs.filter(t => t.id !== id);
    setTabs(remaining);
    if (remaining.length) setActiveTabId(remaining[0].id);
  }

  function onDragStart(e, id) {
    dragTab.current = id;
    e.dataTransfer.setData('application/tab', JSON.stringify(tabs.find(t => t.id === id)));
    e.dataTransfer.effectAllowed = 'move';
  }

  function onDragOver(e, id) {
    e.preventDefault();
    if (dragTab.current !== null && dragTab.current !== id) {
      setTabs(reorder(tabs, dragTab.current, id));
    }
  }

  function onDragEnd(e) {
    const rect = stripRef.current.getBoundingClientRect();
    if (e.clientY > rect.bottom + 20 || e.clientY < rect.top - 20 || e.clientX < rect.left - 20 || e.clientX > rect.right + 20) {
      detachTab(dragTab.current);
    }
    dragTab.current = null;
  }

  function handleExternalDrop(e) {
    e.preventDefault();
    const data = e.dataTransfer.getData('application/tab');
    if (data) {
      try {
        const tab = JSON.parse(data);
        const newTab = { ...tab, id: nextTabId++ };
        setTabs([...tabs, newTab]);
        setActiveTabId(newTab.id);
      } catch (err) {
        console.error(err);
      }
    }
  }

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    function selectionListener() {
      const sel = iframe.contentWindow.getSelection();
      if (sel && sel.toString().trim() !== '') {
        const text = sel.toString();
        if (window.pywebview) {
          window.pywebview.api.on_selection(text);
        }
      }
    }
    iframe.addEventListener('load', () => {
      iframe.contentWindow.document.addEventListener('selectionchange', selectionListener);
    });
  }, [activeTabId, activeTab && activeTab.url]);

  return (
    React.createElement('div', { className: 'browser' },
      React.createElement('div', { className: 'tab-strip', ref: stripRef, onDrop: handleExternalDrop, onDragOver: e => e.preventDefault() },
        tabs.map(tab =>
          React.createElement('div', {
            key: tab.id,
            draggable: true,
            onDragStart: e => onDragStart(e, tab.id),
            onDragOver: e => onDragOver(e, tab.id),
            onDragEnd: onDragEnd,
            onClick: () => setActiveTabId(tab.id),
            className: tab.id === activeTabId ? 'tab active' : 'tab'
          }, tab.title || 'New Tab')
        ),
        React.createElement('button', { onClick: addNewTab }, '+')
      ),
      React.createElement('div', { className: 'toolbar' },
        React.createElement('input', {
          type: 'text',
          value: activeTab ? activeTab.url : '',
          onChange: e => loadUrl(e.target.value),
          placeholder: 'Enter URL',
          id: 'url'
        })
      ),
      activeTab && React.createElement('iframe', { ref: iframeRef, src: activeTab.url, sandbox: 'allow-same-origin allow-scripts allow-forms' })
    )
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(BrowserApp));
