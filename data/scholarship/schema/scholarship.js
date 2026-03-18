const mongoose = require("mongoose");
const scholarDB = require("../../database"); //fix location later
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
        tag_type: Tag,
        tag_value: String
    }],
    essay_required: Boolean,
    date: {
        created: Date,
        due: Date,
        found: {type: Date, default: Date.now()}
    },
    description: String
})

const Scholarship = scholarDB.model('Scholarship', scholarshipSchema);
module.exports = Scholarship;