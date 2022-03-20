module.exports = {
    grants: {
        input: {
            target: '../backend/api.json',
        },
        output: {
            target: './src/api.ts',
            client: 'react-query',
        },
    }
};