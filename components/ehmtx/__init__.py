import logging

from esphome import core
from esphome.components import display, font
import esphome.components.image as espImage
import esphome.config_validation as cv
import esphome.codegen as cg
from esphome.const import CONF_FILE, CONF_ID, CONF_RAW_DATA_ID, CONF_RESIZE, CONF_TYPE
from esphome.core import CORE, HexInt
from esphome.cpp_generator import RawExpression


CONF_ICONS="icons"

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["display"]
MULTI_CONF = True
MAXFRAMES=8

Icons_ = display.display_ns.class_("Animation")


ANIMATION_SCHEMA = cv.Schema({
    cv.Required(CONF_ICONS): cv.All(
        cv.ensure_list(
            {
                cv.Required(CONF_ID): cv.declare_id(Icons_),
                cv.Required(CONF_FILE): cv.file_,
                cv.Optional(CONF_TYPE, default="RGB24"): cv.enum(
                    espImage.IMAGE_TYPE, upper=True
                ),
                cv.GenerateID(CONF_RAW_DATA_ID): cv.declare_id(cg.uint8),
            }
        ), 
        cv.Length(max=64),
)})

CONFIG_SCHEMA = cv.All(font.validate_pillow_installed, ANIMATION_SCHEMA)

CODEOWNERS = ["@lubeda"]

async def to_code(config):

    from PIL import Image
    
    icons = []

    for conf in config[CONF_ICONS]:
        
        path = CORE.relative_config_path(conf[CONF_FILE])
        try:
            image = Image.open(path)
        except Exception as e:
            raise core.EsphomeError(f"Could not load image file {path}: {e}")

        width, height = image.size
        frames = min (image.n_frames,MAXFRAMES)
        
        if conf[CONF_TYPE] == "GRAYSCALE":
            data = [0 for _ in range(height * width * frames)]
            pos = 0
            for frameIndex in range(frames):
                image.seek(frameIndex)
                frame = image.convert("L", dither=Image.NONE)
                pixels = list(frame.getdata())
                if len(pixels) != height * width:
                    raise core.EsphomeError(
                        f"Unexpected number of pixels in {path} frame {frameIndex}: ({len(pixels)} != {height*width})"
                    )
                for pix in pixels:
                    data[pos] = pix
                    pos += 1

        elif conf[CONF_TYPE] == "RGB24":
            data = [0 for _ in range(height * width * 3 * frames)]
            pos = 0
            for frameIndex in range(frames):
                image.seek(frameIndex)
                frame = image.convert("RGB")
                pixels = list(frame.getdata())
                if len(pixels) != height * width:
                    raise core.EsphomeError(
                        f"Unexpected number of pixels in {path} frame {frameIndex}: ({len(pixels)} != {height*width})"
                    )
                for pix in pixels:
                    data[pos] = pix[0]
                    pos += 1
                    data[pos] = pix[1]
                    pos += 1
                    data[pos] = pix[2]
                    pos += 1

        elif conf[CONF_TYPE] == "BINARY":
            width8 = ((width + 7) // 8) * 8
            data = [0 for _ in range((height * width8 // 8) * frames)]
            for frameIndex in range(frames):
                image.seek(frameIndex)
                frame = image.convert("1", dither=Image.NONE)
                for y in range(height):
                    for x in range(width):
                        if frame.getpixel((x, y)):
                            continue
                        pos = x + y * width8 + (height * width8 * frameIndex)
                        data[pos // 8] |= 0x80 >> (pos % 8)

        rhs = [HexInt(x) for x in data]
        prog_arr = cg.progmem_array(conf[CONF_RAW_DATA_ID], rhs)
        cg.new_Pvariable(
            conf[CONF_ID],
            prog_arr,
            width,
            height,
            frames,
            espImage.IMAGE_TYPE[conf[CONF_TYPE]],
        )
        icons.append(str(conf[CONF_ID]))
        
        cg.add(RawExpression("EHMTX_icons[EHMTX_iconcount]= "+ str(conf[CONF_ID])))
        cg.add(RawExpression("EHMTX_iconcount++"))
   
    cg.add_global(RawExpression("display::Animation* EHMTX_icons["+ str(len(icons)) +"]{"+ ",".join(icons)+"}"))
    cg.add_global(RawExpression("const char *EHMTX_iconlist =\""+ ",".join(icons)+"\""))
    cg.add_global(RawExpression("const char *EHMTX_page =\"boot\""));
    cg.add_global(RawExpression("uint8_t EHMTX_iconcount = 0"))
    