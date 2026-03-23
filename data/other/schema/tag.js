const mongoose = require("mongoose");

const tagSchema = new mongoose.Schema({
    name: {type: String, required: true},
    description: {type: String, required: true},
    data_type: {type: String, enum: ["String","Number"], default: "String"},
})

const Tag = mongoose.model('Tag', tagSchema);
module.exports = Tag;