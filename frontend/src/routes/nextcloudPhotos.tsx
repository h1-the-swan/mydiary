import React, { useCallback, useState, useEffect } from "react";
import axios from "axios";
import moment from "moment";
import { useSearchParams } from "react-router-dom";
import { useNextcloudPhotosThumbnailUrls } from "../api";
import { DatePicker, Space } from "antd";

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
      console.log(url);
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
    <main id="container">
      <Space direction="vertical">
        <DatePicker
          defaultValue={dtMoment}
          onChange={(date: any, dateString: string) => {
            setSearchParams({ dt: dateString });
          }}
        />
      </Space>
      {/* <img src="/api/nextcloud/thumbnail_img?url=H1phone_sync/2022/06/22-06-24 19-07-01 4885.jpg" /> */}
      {imgUrls.map((url) => (
        <img src={`/api/nextcloud/thumbnail_img?url=${url}`} alt="" />
      ))}
    </main>
  ) : null;
};

export default NextcloudPhotos;
