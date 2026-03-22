require('dotenv').config()
const express = require('express')
const cors    = require('cors')
const connect = require('./db')

const app = express()

app.use(cors({ origin: 'http://localhost:5173' }))
app.use(express.json())

// Routes
app.use('/api/scholarships', require('./routes/scholarships'))
app.use('/api/users',        require('./routes/users'))
app.use('/api/tags',         require('./routes/tags'))

// Health check
app.get('/api/health', (_, res) => res.json({ ok: true }))

const PORT = process.env.PORT || 3000

connect().then(() => {
  app.listen(PORT, () => console.log(`[api] Running on http://localhost:${PORT}`))
})