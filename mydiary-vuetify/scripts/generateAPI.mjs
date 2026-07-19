import { writeFileSync } from 'fs';

function wait(delay) {
    return new Promise((resolve) => setTimeout(resolve, delay));
}

function fetchRetry(url, delay, tries, fetchOptions = {}) {
    function onError(err) {
        const triesLeft = tries - 1;
        if (!triesLeft) {
            throw err;
        }
        return wait(delay).then(() => fetchRetry(url, delay, triesLeft, fetchOptions));
    }
    return fetch(url, fetchOptions).catch(onError);
}

const openapiUrl =
    process.env.OPENAPI_URL ?? 'http://backend:8888/generate_openapi_json';

fetchRetry(openapiUrl, 1000, 100)
    .then((res) => res.json())
    .then((res) => {
	    writeFileSync("./api.json", JSON.stringify(res));
    });
//     .then(() => {
// 	    orval('../orval.config.js')
//     });