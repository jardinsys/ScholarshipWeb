const router = require('express').Router()
const Tag = require('../../../data/other/schema/tag')

// GET /api/tags
router.get('/', async (req, res) => {
  try {
    const tags = await Tag.find({}).sort({ name: 1 })
    res.json(tags)
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch tags' })
  }
})

// POST /api/tags
router.post('/', async (req, res) => {
  try {
    const tag = await Tag.create(req.body)
    res.status(201).json(tag)
  } catch (err) {
    res.status(500).json({ error: 'Failed to create tag' })
  }
})

module.exports = router