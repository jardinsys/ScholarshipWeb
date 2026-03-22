const router = require('express').Router()
const Scholarship = require('../../../data/scholarship/schema/scholarship')

// GET /api/scholarships
// Supports ?search=, ?no_essay=true, ?limit=20&skip=0
router.get('/', async (req, res) => {
  try {
    const { search, no_essay, limit = 20, skip = 0 } = req.query
    const query = {}

    if (search) {
      query.$or = [
        { name:     { $regex: search, $options: 'i' } },
        { provider: { $regex: search, $options: 'i' } },
        { summary:  { $regex: search, $options: 'i' } },
      ]
    }

    if (no_essay === 'true') {
      query.essay_required = false
    }

    const scholarships = await Scholarship.find(query)
      .populate('tags.tag_type', 'name description')
      .sort({ 'date.found': -1 })   // newest first
      .limit(Number(limit))
      .skip(Number(skip))

    const total = await Scholarship.countDocuments(query)

    res.json({ scholarships, total })
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: 'Failed to fetch scholarships' })
  }
})

// GET /api/scholarships/:id
router.get('/:id', async (req, res) => {
  try {
    const s = await Scholarship.findById(req.params.id)
      .populate('tags.tag_type', 'name description')
    if (!s) return res.status(404).json({ error: 'Not found' })
    res.json(s)
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch scholarship' })
  }
})

module.exports = router