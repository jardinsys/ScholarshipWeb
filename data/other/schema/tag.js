const mongoose = require("mongoose");
const scholarDB = require("../../database"); //fix location later

const tagSchema = new mongoose.Schema({
    _id: { type: mongoose.Schema.Types.ObjectId, unique: true},
    name: {type: String, required: true},
    description: {type: String, required: true},
    options: [String]
})

const Tag = scholarDB.model('Tag', tagSchema);
module.exports = Tag;