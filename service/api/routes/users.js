const router = require('express').Router()
const User = require('../../../data/user/schema/user')
const Scholarship = require('../../../data/scholarship/schema/scholarship')

// AUTH
// POST /api/users/register
router.post('/register', async (req, res) => {
  try {
    const { username } = req.body
    if (!username?.trim()) return res.status(400).json({ error: 'Username is required' })

    const existing = await User.findOne({ username: username.trim() })
    if (existing) return res.status(409).json({ error: 'Username already taken' })

    const user = await User.create({
      username:    username.trim(),
      displayname: username.trim(),
    })

    res.status(201).json(user)
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: 'Failed to create user' })
  }
})

// POST /api/users/login
router.post('/login', async (req, res) => {
  try {
    const { username } = req.body
    if (!username?.trim()) return res.status(400).json({ error: 'Username is required' })

    const user = await User.findOne({ username: username.trim() })
      .populate('tags.tag_type', 'name description')
    if (!user) return res.status(404).json({ error: 'User not found' })

    res.json(user)
  } catch (err) {
    res.status(500).json({ error: 'Failed to log in' })
  }
})

// USER PROFILES
// GET /api/users/:id
router.get('/:id', async (req, res) => {
  try {
    const user = await User.findById(req.params.id)
      .populate('tags.tag_type', 'name description')
      .populate('saved_scholarships', 'name provider amount date')
    if (!user) return res.status(404).json({ error: 'User not found' })
    res.json(user)
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch user' })
  }
})

// PUT /api/users/:id
router.put('/:id', async (req, res) => {
  try {
    const { displayname, username, bio } = req.body
    const user = await User.findByIdAndUpdate(
      req.params.id,
      { displayname, username, bio },
      { new: true }
    )
    res.json(user)
  } catch (err) {
    res.status(500).json({ error: 'Failed to update user' })
  }
})

// TAGS
// GET /api/users/:id/tags
router.get('/:id/tags', async (req, res) => {
  try {
    const user = await User.findById(req.params.id)
      .populate('tags.tag_type', 'name description')
    if (!user) return res.status(404).json({ error: 'User not found' })
    res.json(user.tags)
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch tags' })
  }
})

// POST /api/users/:id/tags
router.post('/:id/tags', async (req, res) => {
  try {
    const { tag_type, tag_value } = req.body
    const user = await User.findByIdAndUpdate(
      req.params.id,
      { $push: { tags: { tag_type, tag_value } } },
      { new: true }
    ).populate('tags.tag_type', 'name description')
    res.json(user)
  } catch (err) {
    res.status(500).json({ error: 'Failed to add tag' })
  }
})

// DELETE /api/users/:id/tags/:tagTypeId
router.delete('/:id/tags/:tagTypeId', async (req, res) => {
  try {
    const user = await User.findByIdAndUpdate(
      req.params.id,
      { $pull: { tags: { tag_type: req.params.tagTypeId } } },
      { new: true }
    ).populate('tags.tag_type', 'name description')
    res.json(user)
  } catch (err) {
    res.status(500).json({ error: 'Failed to remove tag' })
  }
})

// RECCOMENDATIONS
/**
 * GET /api/users/:id/matches
 *
 * Algorithm Logic:
 *   1. Load user's tags (tag_type + tag_value pairs).
 *   2. Fetch all scholarships that share at least one tag_type with the user.
 *   3. Score each scholarship:
 *        - +2 points for each tag_type match
 *        - +1 bonus point if the tag_value also matches (case-insensitive)
 *   4. Sort by score descending, return top 50 with a matchScore % field.
 */
router.get('/:id/matches', async (req, res) => {
  try {
    const user = await User.findById(req.params.id)
      .populate('tags.tag_type', 'name description')
    if (!user) return res.status(404).json({ error: 'User not found' })

    if (!user.tags || user.tags.length === 0) {
      // No tags — fall back to newest scholarships
      const fallback = await Scholarship.find({})
        .populate('tags.tag_type', 'name description')
        .sort({ 'date.found': -1 })
        .limit(20)
      return res.json(fallback)
    }

    // Build lookup maps from user tags
    // tagTypeId -> tag_value (lowercase)
    const userTagMap = new Map()
    for (const t of user.tags) {
      const typeId = String(t.tag_type?._id ?? t.tag_type)
      const value  = String(t.tag_value ?? '').toLowerCase().trim()
      userTagMap.set(typeId, value)
    }

    const userTagTypeIds = [...userTagMap.keys()]

    // Fetch scholarships that share at least one tag_type
    const candidates = await Scholarship.find({
      'tags.tag_type': { $in: userTagTypeIds },
    })
      .populate('tags.tag_type', 'name description')
      .limit(200)

    // Score each candidate
    const maxPossibleScore = userTagTypeIds.length * 3  // 2 type + 1 value per tag
    const scored = candidates.map(s => {
      let score = 0
      for (const t of s.tags) {
        const typeId = String(t.tag_type?._id ?? t.tag_type)
        if (userTagMap.has(typeId)) {
          score += 2  // tag type matched
          const sValue = String(t.tag_value ?? '').toLowerCase().trim()
          const uValue = userTagMap.get(typeId)
          if (sValue && uValue && sValue === uValue) {
            score += 1  // exact value match bonus
          }
        }
      }
      // matchScore as a percentage (0–100)
      const matchScore = Math.round((score / Math.max(maxPossibleScore, 1)) * 100)
      return { scholarship: s.toObject(), score, matchScore }
    })

    scored.sort((a, b) => b.score - a.score)

    const results = scored.slice(0, 50).map(({ scholarship, matchScore }) => ({
      ...scholarship,
      matchScore,
    }))

    res.json(results)
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: 'Failed to compute matches' })
  }
})

// ─── Saved scholarships ────────────────────────────────────────────────────────

// GET /api/users/:id/saved
router.get('/:id/saved', async (req, res) => {
  try {
    const user = await User.findById(req.params.id)
      .populate('saved_scholarships')
    if (!user) return res.status(404).json({ error: 'User not found' })
    res.json(user.saved_scholarships)
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch saved scholarships' })
  }
})

// POST /api/users/:id/saved/:scholarshipId
router.post('/:id/saved/:scholarshipId', async (req, res) => {
  try {
    const user = await User.findByIdAndUpdate(
      req.params.id,
      { $addToSet: { saved_scholarships: req.params.scholarshipId } },
      { new: true }
    ).populate('saved_scholarships', 'name provider amount date')
    res.json(user.saved_scholarships)
  } catch (err) {
    res.status(500).json({ error: 'Failed to save scholarship' })
  }
})

// DELETE /api/users/:id/saved/:scholarshipId
router.delete('/:id/saved/:scholarshipId', async (req, res) => {
  try {
    const user = await User.findByIdAndUpdate(
      req.params.id,
      { $pull: { saved_scholarships: req.params.scholarshipId } },
      { new: true }
    ).populate('saved_scholarships', 'name provider amount date')
    res.json(user.saved_scholarships)
  } catch (err) {
    res.status(500).json({ error: 'Failed to unsave scholarship' })
  }
})

module.exports = router