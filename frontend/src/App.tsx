import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';

interface Draft {
  title: string;
  content: string;
  instructions: string;
}

interface Metadata {
  safety_score?: number;
  empathy_score?: number;
  clarity_score?: number;
  total_revisions: number;
}

interface ConversationItem {
  type: 'user' | 'assistant';
  content: string;
  draft?: Draft;
  metadata?: Metadata;
}

// Markdown component styles for consistent formatting
const markdownComponents = {
  h1: ({ node, ...props }: any) => <h1 style={{ fontSize: '24px', fontWeight: 600, marginTop: '24px', marginBottom: '12px', color: '#111827' }} {...props} />,
  h2: ({ node, ...props }: any) => <h2 style={{ fontSize: '20px', fontWeight: 600, marginTop: '20px', marginBottom: '10px', color: '#111827' }} {...props} />,
  h3: ({ node, ...props }: any) => <h3 style={{ fontSize: '18px', fontWeight: 600, marginTop: '18px', marginBottom: '8px', color: '#111827' }} {...props} />,
  h4: ({ node, ...props }: any) => <h4 style={{ fontSize: '16px', fontWeight: 600, marginTop: '16px', marginBottom: '8px', color: '#111827' }} {...props} />,
  p: ({ node, ...props }: any) => <p style={{ marginBottom: '12px', marginTop: 0 }} {...props} />,
  ul: ({ node, ...props }: any) => <ul style={{ marginBottom: '12px', marginTop: '8px', paddingLeft: '24px' }} {...props} />,
  ol: ({ node, ...props }: any) => <ol style={{ marginBottom: '12px', marginTop: '8px', paddingLeft: '24px' }} {...props} />,
  li: ({ node, ...props }: any) => <li style={{ marginBottom: '6px' }} {...props} />,
  strong: ({ node, ...props }: any) => <strong style={{ fontWeight: 600, color: '#111827' }} {...props} />,
  em: ({ node, ...props }: any) => <em style={{ fontStyle: 'italic' }} {...props} />,
  code: ({ node, ...props }: any) => <code style={{ backgroundColor: '#f3f4f6', padding: '2px 6px', borderRadius: '4px', fontSize: '14px', fontFamily: 'monospace' }} {...props} />,
  pre: ({ node, ...props }: any) => <pre style={{ backgroundColor: '#f3f4f6', padding: '12px', borderRadius: '8px', overflow: 'auto', marginBottom: '12px' }} {...props} />,
  blockquote: ({ node, ...props }: any) => <blockquote style={{ borderLeft: '4px solid #e5e7eb', paddingLeft: '16px', marginLeft: 0, marginBottom: '12px', color: '#6b7280' }} {...props} />,
  hr: ({ node, ...props }: any) => <hr style={{ border: 'none', borderTop: '1px solid #e5e7eb', margin: '20px 0' }} {...props} />,
};

function App() {
  const [message, setMessage] = useState('');
  const [threadId] = useState(`thread-${Date.now()}`);
  const [conversation, setConversation] = useState<ConversationItem[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation]);

  const handleSendMessage = async () => {
    if (!message.trim() || isProcessing) return;

    const userMessage = message;
    setConversation(prev => [...prev, { type: 'user', content: userMessage }]);
    setMessage('');
    setIsProcessing(true);

    try {
      const response = await fetch('http://localhost:8000/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage, thread_id: threadId })
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'complete') {
                const stateResponse = await fetch(`http://localhost:8000/state/${threadId}`);
                const state = await stateResponse.json();
                setConversation(prev => [...prev, {
                  type: 'assistant',
                  content: 'CBT Exercise Created',
                  draft: state.current_draft,
                  metadata: state.metadata
                }]);
                break;
              }
            } catch (e) { }
          }
        }
      }
    } catch (error) {
      setConversation(prev => [...prev, { type: 'assistant', content: 'Error processing request' }]);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', fontFamily: 'system-ui, sans-serif' }}>
      {/* Header */}
      <div style={{ padding: '16px 24px', borderBottom: '1px solid #e5e7eb', backgroundColor: 'white' }}>
        <h1
          onClick={() => window.location.reload()}
          style={{ fontSize: '20px', margin: 0, color: '#1f2937', cursor: 'pointer', userSelect: 'none' }}
        >
          Cerina Foundry
        </h1>
      </div>

      {/* Chat Area */}
      <div style={{ flex: 1, overflowY: 'auto', backgroundColor: 'white' }}>
        <div style={{ maxWidth: '800px', margin: '0 auto', padding: '32px 24px' }}>
          {conversation.length === 0 && (
            <div style={{ textAlign: 'center', paddingTop: '80px' }}>
              <h2 style={{ fontSize: '36px', fontWeight: 300, color: '#1f2937', marginBottom: '16px' }}>Hello</h2>
              <p style={{ color: '#6b7280' }}>How can I help you create a CBT exercise today?</p>
            </div>
          )}

          {conversation.map((item, idx) => (
            <div key={idx} style={{ marginBottom: '32px' }}>
              {item.type === 'user' ? (
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <div style={{ backgroundColor: '#f3f4f6', borderRadius: '9999px', padding: '12px 20px', maxWidth: '600px' }}>
                    <p style={{ margin: 0, color: '#1f2937' }}>{item.content}</p>
                  </div>
                </div>
              ) : (
                <div>
                  {item.draft ? (
                    <div>
                      <h2 style={{ fontSize: '20px', fontWeight: 400, color: '#111827', marginBottom: '12px' }}>
                        {item.draft.title}
                      </h2>

                      {item.metadata && (
                        <div style={{ display: 'flex', gap: '12px', fontSize: '12px', color: '#6b7280', marginBottom: '16px' }}>
                          <span>Safety {item.metadata.safety_score?.toFixed(1)}</span>
                          <span>Empathy {item.metadata.empathy_score?.toFixed(1)}</span>
                          <span>Clarity {item.metadata.clarity_score?.toFixed(1)}</span>
                          <span>{item.metadata.total_revisions} revisions</span>
                        </div>
                      )}

                      <div style={{ color: '#374151', fontSize: '15px', lineHeight: '1.7', marginBottom: '16px' }}>
                        <ReactMarkdown components={markdownComponents}>
                          {item.draft.instructions}
                        </ReactMarkdown>
                      </div>

                      <div style={{ color: '#374151', fontSize: '15px', lineHeight: '1.7' }}>
                        <ReactMarkdown components={markdownComponents}>
                          {item.draft.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                  ) : (
                    <p style={{ color: '#374151', fontSize: '15px', lineHeight: '1.7' }}>{item.content}</p>
                  )}
                </div>
              )}
            </div>
          ))}

          {isProcessing && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6b7280' }}>
              <span style={{ fontSize: '14px' }}>Agents are collaborating...</span>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div style={{ borderTop: '1px solid #e5e7eb', backgroundColor: 'white', padding: '24px' }}>
        <div style={{ maxWidth: '800px', margin: '0 auto', display: 'flex', gap: '12px', backgroundColor: '#f3f4f6', borderRadius: '24px', padding: '12px 24px', alignItems: 'center' }}>
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Ask Cerina Foundry"
            disabled={isProcessing}
            style={{ flex: 1, border: 'none', backgroundColor: 'transparent', outline: 'none', fontSize: '15px', color: '#1f2937' }}
          />
          <button
            onClick={handleSendMessage}
            disabled={isProcessing || !message.trim()}
            style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#6b7280', fontSize: '24px', padding: 0 }}
          >
            ➤
          </button>
        </div>
        <p style={{ textAlign: 'center', fontSize: '12px', color: '#9ca3af', marginTop: '12px' }}>
          Cerina Foundry uses AI agents. Verify important information.
        </p>
      </div>
    </div>
  );
}

export default App;

