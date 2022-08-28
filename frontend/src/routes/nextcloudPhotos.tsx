import React, { useCallback, useState, useEffect } from "react";
import axios from 'axios';
import moment from "moment";
import { useSearchParams } from "react-router-dom";
import { useNextcloudPhotosThumbnailUrls } from "../api";

const NextcloudPhotos = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [imgObjectURLs, setImgObjectURLs] = useState<any[]>([]);
  if (!searchParams.get("dt")) {
    setSearchParams({ dt: "yesterday" });
  }
  const dt = searchParams.get("dt") || "yesterday";
  let dtMoment: moment.Moment;
  if (dt === "today") {
    dtMoment = moment();
  } else if (dt === "yesterday") {
    dtMoment = moment().subtract(1, "days");
  } else {
    dtMoment = moment(dt);
  }
  let { data: imgUrls, isLoading } = useNextcloudPhotosThumbnailUrls(dt, {
    query: {
      select: (d) => d.data,
    },
  });
  useEffect(() => console.log(imgUrls), [imgUrls]);
  useEffect(() => {
    const imgs = imgUrls?.map((url) => {
      console.log(axios.get(`/nextcloud/thumbnail_img/?url="${url}"`));
        // .then((response) => response.blob())
        // .then((imgBlob) => {
        //   const imgObjectURL = URL.createObjectURL(imgBlob);
        //   console.log(imgObjectURL);
        //   console.log(imgBlob);
        //   const image = document.createElement("img");
        //   image.src = imgObjectURL;

        //   const container = document.getElementById("container");
        //   if (container) {
        //     container.append(image);
        //   }
        // });
    });
  }, [imgUrls]);
  return isLoading ? (
    <span>Loading...</span>
  ) : imgUrls ? (
    <main id="container"></main>
  ) : null;
};

export default NextcloudPhotos;
