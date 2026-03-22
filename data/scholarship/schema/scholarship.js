const mongoose = require("mongoose");
const Snowflake = require('snowflake-id').default;
const snowflake = new Snowflake({
    mid: 1,  // Machine ID
    offset: 0
});

const scholarshipSchema = new mongoose.Schema({
    id: { type: String, default: () => snowflake.generate(), unique: true},
    name: String, 
    provider: String, 
    url: String,
    tags: [{
        tag_type: { type: mongoose.Schema.Types.ObjectId, ref: 'Tag', required: true },
        tag_value: { type: mongoose.Schema.Types.Mixed, required: true }
    }],
    essay_required: Boolean,
    date: {
        created: Date,
        due: Date,
        found: {type: Date, default: Date.now()}
    },
    description: String
})

const Scholarship = mongoose.model('Scholarship', scholarshipSchema);
module.exports = Scholarship;