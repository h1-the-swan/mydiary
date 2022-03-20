module.exports = {
    grants: {
        input: {
            target: '../notebooks/api.json',
        },
        output: {
            target: './src/api.ts',
            client: 'react-query',
        },
    }
};