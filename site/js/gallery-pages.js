/**
 * Auto-generated gallery pages map from site/structure.json.
 * Do not edit manually.
 */
window.resolveGalleryPageEntries = window.resolveGalleryPageEntries || function resolveGalleryPageEntries(value, fallbackHtml) {
  if (Array.isArray(value)) return value;
  if (!value || !Array.isArray(value.p)) return [];
  if (Array.isArray(value.__pages)) return value.__pages;
  const normalize = (path) => String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
  const join = (base, path) => {
    const normalizedPath = normalize(path);
    if (!normalizedPath) return "";
    if (normalizedPath.startsWith("contents/") || normalizedPath.startsWith("thumbnail/")) return normalizedPath;
    const normalizedBase = normalize(base).replace(/\/+$/, "");
    return normalizedBase ? normalizedBase + "/" + normalizedPath : normalizedPath;
  };
  const stem = (path) => {
    const normalizedPath = normalize(path);
    const fileName = normalizedPath.split("/").pop() || normalizedPath;
    return fileName.replace(/\.[^.]+$/, "");
  };
  const ext = (path) => {
    const match = /\.([^.]+)$/.exec(String(path || ""));
    return match ? match[1].toLowerCase() : "";
  };
  const base = value.b || "";
  const thumbBase = value.t || "";
  const html = join("", fallbackHtml || "");
  value.__pages = value.p.map((item) => {
    if (!Array.isArray(item) || item.length === 0) return null;
    if (item[0] === "v") {
      const video = join(base, item[1]);
      return { type: "video", video, html, thumbNumber: Number(item[2]) > 0 ? Number(item[2]) : null, label: item[3] || stem(item[1] || video), ext: String(item[4] || ext(item[1] || video)).toLowerCase() };
    }
    const image = join(base, item[1]);
    const thumbnail = item.length >= 3 && item[2] ? join(thumbBase || base, item[2]) : join(thumbBase || base, item[1]);
    return { type: "image", image, thumbnail, html, label: stem(item[1] || image) };
  }).filter(Boolean);
  return value.__pages;
};
window.galleryPagesMap = {"photo/[うんぱい][20220628] uP":{"b":"contents/photo/[うんぱい][20220628] uP","p":[["i","00001.jpg","001.jpg"],["i","00002.jpg","002.jpg"],["i","00003.jpg","003.jpg"],["i","00004.jpg","004.jpg"],["i","00005.jpg","005.jpg"],["i","00006.jpg","006.jpg"],["i","00007.jpg","007.jpg"],["i","00008.jpg","008.jpg"],["i","00009.jpg","009.jpg"],["i","00010.jpg","010.jpg"],["i","00011.jpg","011.jpg"],["i","00012.jpg","012.jpg"],["i","00013.jpg","013.jpg"],["i","00014.jpg","014.jpg"],["i","00015.jpg","015.jpg"],["i","00016.jpg","016.jpg"],["i","00017.jpg","017.jpg"],["i","00018.jpg","018.jpg"],["i","00019.jpg","019.jpg"],["i","00020.jpg","020.jpg"],["i","00021.jpg","021.jpg"],["i","00022.jpg","022.jpg"],["i","00023.jpg","023.jpg"],["i","00024.jpg","024.jpg"],["i","00025.jpg","025.jpg"],["i","00026.jpg","026.jpg"],["i","00027.jpg","027.jpg"],["i","00028.jpg","028.jpg"],["i","00029.jpg","029.jpg"],["i","00030.jpg","030.jpg"],["i","00031.jpg","031.jpg"],["i","00032.jpg","032.jpg"],["i","00033.jpg","033.jpg"],["i","00034.jpg","034.jpg"],["i","00035.jpg","035.jpg"],["i","00036.jpg","036.jpg"],["i","00037.jpg","037.jpg"],["i","00038.jpg","038.jpg"],["i","00039.jpg","039.jpg"],["i","00040.jpg","040.jpg"],["i","00041.jpg","041.jpg"],["i","00042.jpg","042.jpg"],["i","00043.jpg","043.jpg"],["i","00044.jpg","044.jpg"],["i","00045.jpg","045.jpg"],["i","00046.jpg","046.jpg"],["i","00047.jpg","047.jpg"],["i","00048.jpg","048.jpg"],["i","00049.jpg","049.jpg"],["i","00050.jpg","050.jpg"],["i","00051.jpg","051.jpg"],["i","00052.jpg","052.jpg"],["i","00053.jpg","053.jpg"],["i","00054.jpg","054.jpg"],["i","00055.jpg","055.jpg"],["i","00056.jpg","056.jpg"],["i","00057.jpg","057.jpg"],["i","00058.jpg","058.jpg"],["i","00059.jpg","059.jpg"],["i","00060.jpg","060.jpg"],["i","00061.jpg","061.jpg"],["i","00062.jpg","062.jpg"],["i","00063.jpg","063.jpg"],["i","00064.jpg","064.jpg"],["i","00065.jpg","065.jpg"],["i","00066.jpg","066.jpg"],["i","00067.jpg","067.jpg"],["i","00068.jpg","068.jpg"],["i","00069.jpg","069.jpg"],["i","00070.jpg","070.jpg"],["i","00071.jpg","071.jpg"],["i","00072.jpg","072.jpg"],["i","00073.jpg","073.jpg"],["i","00074.jpg","074.jpg"],["i","00075.jpg","075.jpg"],["i","00076.jpg","076.jpg"],["i","00077.jpg","077.jpg"],["i","00078.jpg","078.jpg"],["i","00079.jpg","079.jpg"],["i","00080.jpg","080.jpg"],["i","00081.jpg","081.jpg"],["i","00082.jpg","082.jpg"],["i","00083.jpg","083.jpg"],["i","00084.jpg","084.jpg"],["i","00085.jpg","085.jpg"],["i","00086.jpg","086.jpg"],["i","00087.jpg","087.jpg"],["i","00088.jpg","088.jpg"],["i","00089.jpg","089.jpg"],["i","00090.jpg","090.jpg"],["i","00091.jpg","091.jpg"],["i","00092.jpg","092.jpg"],["i","00093.jpg","093.jpg"],["i","00094.jpg","094.jpg"],["i","00095.jpg","095.jpg"],["i","00096.jpg","096.jpg"],["i","00097.jpg","097.jpg"],["i","00098.jpg","098.jpg"],["i","00099.jpg","099.jpg"],["i","00100.jpg","100.jpg"],["i","00101.jpg","101.jpg"],["i","00102.jpg","102.jpg"],["i","00103.jpg","103.jpg"],["i","00104.jpg","104.jpg"],["i","00105.jpg","105.jpg"],["i","00106.jpg","106.jpg"],["i","00107.jpg","107.jpg"],["i","00108.jpg","108.jpg"],["i","00109.jpg","109.jpg"],["i","00110.jpg","110.jpg"],["i","00111.jpg","111.jpg"],["i","00112.jpg","112.jpg"],["i","00113.jpg","113.jpg"],["i","00114.jpg","114.jpg"]],"s":"b635597a9d337ea8f1e0e12f6a1fdd722a5da1af","t":"thumbnail/photo/[うんぱい][20220628] uP"}};
