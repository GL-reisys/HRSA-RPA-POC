'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { 
  Box, 
  Paper, 
  Typography, 
  TextField,
  Button,
  IconButton,
  Chip,
  CircularProgress,
  Divider
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import RefreshIcon from '@mui/icons-material/Refresh';
import DescriptionIcon from '@mui/icons-material/Description';

async function readJsonOrText(response) {
  const body = await response.text();

  if (!body) {
    return null;
  }

  try {
    return JSON.parse(body);
  } catch {
    return body;
  }
}

export default function ChatInterface({ 
  fileId, 
  fileName, 
  formType,
  formData, 
  validationErrors, 
  initialResponse,
  chatHistory: initialChatHistory,
  onReset 
}) {
  const [message, setMessage] = useState('');
  const [chatHistory, setChatHistory] = useState(() => {
    // Add greeting message at the start
    const greeting = {
      role: 'assistant',
      content: "Hello! I'm AVA, your Application Validation Assistant. I've analyzed your form and I'm ready to help you with any questions.",
      timestamp: new Date().toISOString(),
      isGreeting: true
    };
    return [greeting, ...(initialChatHistory || [])];
  });
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory]);

  const setInputRef = useCallback((node) => {
    if (node && !sending) {
      node.focus();
    }
  }, [sending]);

  const handleSendMessage = async () => {
    if (!message.trim() || sending) return;

    const userMessage = message.trim();
    setMessage('');
    setSending(true);

    const newUserMessage = {
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString()
    };

    setChatHistory(prev => [...prev, newUserMessage]);

    try {
      const response = await fetch('/api/chat/message', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          file_id: fileId,
          message: userMessage,
          chat_history: chatHistory
        }),
      });

      const payload = await readJsonOrText(response);

      if (!response.ok) {
        const message =
          (payload && typeof payload === 'object' && payload.error) ||
          (typeof payload === 'string' && payload) ||
          'Failed to send message';
        throw new Error(message);
      }

      if (!payload || typeof payload !== 'object') {
        throw new Error('Chat returned an unexpected response.');
      }

      const result = payload;

      const assistantMessage = {
        role: 'assistant',
        content: result.response,
        timestamp: new Date().toISOString()
      };

      setChatHistory(prev => [...prev, assistantMessage]);

    } catch (err) {
      console.error('Error sending message:', err);
      const errorMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString()
      };
      setChatHistory(prev => [...prev, errorMessage]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const validationStatus = validationErrors.length === 0 ? 'PASSED' : 'FAILED';

  return (
    <Box sx={{ 
      minHeight: '100vh',
      backgroundColor: '#f5f7f9',
      p: 3 
    }}>
      <Box sx={{ maxWidth: 1200, mx: 'auto' }}>
      <Paper elevation={2} sx={{ p: 3, mb: 3, backgroundColor: '#1e4d5a' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 1, justifyContent: 'center' }}>
            <Typography variant="h5" sx={{ fontWeight: 600, color: '#ffffff' }}>
              AVA Chat Assistant
            </Typography>
            <Chip 
              icon={<DescriptionIcon />}
              label={`${formType || 'SF-424'} - ${fileName}`} 
              color="primary" 
              variant="outlined"
              sx={{ backgroundColor: '#ffffff' }}
            />
            <Chip 
              label={validationStatus}
              color={validationStatus === 'PASSED' ? 'success' : 'error'}
              size="small"
            />
          </Box>
          <IconButton onClick={onReset} sx={{ color: '#ffffff' }} title="Upload new form">
            <RefreshIcon />
          </IconButton>
        </Box>
      </Paper>

      <Paper elevation={1} sx={{ height: 'calc(100vh - 200px)', display: 'flex', flexDirection: 'column' }}>
        <Box 
          sx={{ 
            flex: 1, 
            overflowY: 'auto', 
            p: 3,
            backgroundColor: '#ffffff'
          }}
        >
          {chatHistory.map((msg, index) => (
            <Box 
              key={index}
              sx={{ 
                mb: 2,
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
              }}
            >
              <Paper
                elevation={msg.role === 'user' ? 2 : 3}
                sx={{
                  p: 2.5,
                  maxWidth: '70%',
                  backgroundColor: msg.role === 'user' 
                    ? '#e8f4f8' 
                    : '#ffffff',
                  background: msg.role === 'user' 
                    ? '#e8f4f8' 
                    : '#ffffff',
                  color: '#000',
                  border: msg.role === 'user' ? '1px solid #90caf9' : '1px solid #d0d0d0',
                  borderRadius: 2,
                  boxShadow: msg.role === 'assistant' && (index === 1 || msg.content.includes('Not ready for submission') || msg.content.includes('Ready for submission') || msg.content.includes('Fields validated successfully') || msg.content.includes('Need to Fix'))
                    ? '0 4px 12px rgba(0,0,0,0.1)'
                    : undefined
                }}
              >
                {msg.role === 'assistant' && !msg.isGreeting && (
                  <Typography 
                    variant="caption" 
                    sx={{ 
                      color: '#666',
                      display: 'block',
                      mb: 0.5
                    }}
                  >
                    {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </Typography>
                )}
                
                {msg.role === 'user' && index === 1 && (
                  <Box sx={{ mb: 1, p: 1, backgroundColor: '#c8e6c9', borderRadius: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="caption" sx={{ color: '#2e7d32', fontWeight: 600 }}>
                      [PDF]
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#2e7d32' }}>
                      {fileName}
                    </Typography>
                  </Box>
                )}
                
                <Typography 
                  variant="body1"
                  dangerouslySetInnerHTML={{ __html: msg.content }}
                  sx={{
                    '& strong': { fontWeight: 700 },
                    '& br': { display: 'block', content: '""', marginTop: '0.5em' },
                    lineHeight: 1.6
                  }}
                />
                
                {msg.role === 'user' && index > 1 && (
                  <Typography 
                    variant="caption" 
                    sx={{ 
                      color: '#666',
                      display: 'block',
                      mt: 0.5,
                      textAlign: 'right'
                    }}
                  >
                    {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </Typography>
                )}
              </Paper>
            </Box>
          ))}
          {sending && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <CircularProgress size={20} />
              <Typography variant="body2" color="text.secondary">
                AVA is typing...
              </Typography>
            </Box>
          )}
          <div ref={messagesEndRef} />
        </Box>

        <Divider />

        <Box sx={{ p: 2, backgroundColor: '#f5f5f5' }}>
          <Box sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            mb: 2,
            p: 1.5,
            backgroundColor: '#c8e6c9',
            borderRadius: 1
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" sx={{ color: '#2e7d32', fontWeight: 600 }}>
                [PDF]
              </Typography>
              <Typography variant="body2" sx={{ color: '#2e7d32' }}>
                {fileName}
              </Typography>
            </Box>
            <Button
              variant="contained"
              color="error"
              size="small"
              onClick={onReset}
            >
              Remove
            </Button>
          </Box>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              fullWidth
              multiline
              maxRows={3}
              placeholder="Type your message here..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={sending}
              variant="outlined"
              size="small"
              inputRef={setInputRef}
              sx={{ backgroundColor: '#fff' }}
            />
            <Button
              variant="contained"
              onClick={handleSendMessage}
              disabled={!message.trim() || sending}
              sx={{ minWidth: 100, height: 40 }}
            >
              Send
            </Button>
          </Box>
        </Box>
      </Paper>
      </Box>
    </Box>
  );
}
