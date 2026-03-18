# Quick Start Guide - @orcapt/sdk

Get started with the Orca SDK in minutes!

## Installation

```bash
npm install @orcapt/sdk
```

For Express integration:

```bash
npm install @orcapt/sdk express
```

## Basic Example

```javascript
const { OrcaHandler } = require('@orcapt/sdk');

// Initialize handler
const orca = new OrcaHandler();

// Process a message
async function handleMessage(data) {
  try {
    // Your AI logic here
    const response = 'Hello from AI!';

    // Send response to Orca
    await orca.completeResponse(data, response);
  } catch (error) {
    await orca.sendError(data, error.message);
  }
}
```

## With Express

```javascript
const { createOrcaApp, addStandardEndpoints, OrcaHandler } = require('@orcapt/sdk');

// Create app
const app = createOrcaApp({ title: 'My AI Agent' });
const orca = new OrcaHandler();

// Define message handler
async function processMessage(data) {
  const response = `You said: ${data.message}`;
  await orca.completeResponse(data, response);
}

// Add endpoints
addStandardEndpoints(app, {
  orcaHandler: orca,
  processMessageFunc: processMessage
});

// Start server
app.listen(8000, () => console.log('Server running on port 8000'));
```

## Using Variables & Memory

```javascript
const { Variables, MemoryHelper } = require('@orcapt/sdk');

async function processMessage(data) {
  // Access environment variables
  const vars = new Variables(data.variables);
  const apiKey = vars.get('OPENAI_API_KEY');

  // Access user memory
  const memory = new MemoryHelper(data.memory);
  const userName = memory.getName();
  const userGoals = memory.getGoals();

  // Create personalized response
  let response = `Hello ${userName}!`;
  if (memory.hasGoals()) {
    response += ` I see you want to ${userGoals.join(', ')}`;
  }

  await orca.completeResponse(data, response);
}
```

## Streaming Responses

```javascript
async function processMessage(data) {
  const words = 'Hello from streaming AI!'.split(' ');

  // Stream each word
  for (const word of words) {
    await orca.streamChunk(data, word + ' ');
    await new Promise(r => setTimeout(r, 100));
  }

  // Complete the response
  await orca.completeResponse(data, 'Hello from streaming AI!');
}
```

## Development Mode

Set the environment variable for local development:

```bash
export ORCA_DEV_MODE=true
```

Or initialize directly:

```javascript
const orca = new OrcaHandler(true); // Dev mode
```

## Next Steps

- Check out the full [README.md](README.md) for detailed documentation
- See [example.js](example.js) for more examples
- Run `node test-package.js` to test the installation

## Need Help?

- 📚 [Full Documentation](README.md)
- 🐛 [Report Issues](https://github.com/orcapt/orca-npm/issues)
- 💬 [Ask Questions](https://github.com/orcapt/orca-npm/discussions)
