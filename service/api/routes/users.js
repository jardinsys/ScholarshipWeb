const router = require('express').Router()
const User = require('../../../data/user/schema/user')

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

// PUT /api/users/:id  — update displayname, username, bio
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

// GET /api/users/:id/tags
router.get('/:id/tags', async (req, res) => {
  try {
    const user = await User.findById(req.params.id)
      .populate('tags.tag_type', 'name description')
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

// POST /api/users/:id/saved/:scholarshipId  — save a scholarship
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

// DELETE /api/users/:id/saved/:scholarshipId  — unsave
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

// GET /api/users/:id/saved  — get saved scholarships
router.get('/:id/saved', async (req, res) => {
  try {
    const user = await User.findById(req.params.id)
      .populate('saved_scholarships')
    res.json(user.saved_scholarships)
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch saved scholarships' })
  }
})

module.exports = router